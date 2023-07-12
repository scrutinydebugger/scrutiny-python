__all__ = ['Client']


from scrutiny.sdk.definitions import *
from scrutiny.sdk.watchable_handle import WatchableHandle
import scrutiny.sdk.exceptions as sdk_exceptions
from scrutiny.core.basic_types import *
from scrutiny.tools.timer import Timer
import scrutiny.sdk._api_parser as api_parser
from scrutiny.sdk._write_request import WriteRequest
from scrutiny.server.api import typing as api_typing
from scrutiny.server.api import API

import logging
import traceback
import threading
import socket
import websockets
import websockets.sync.client
import websockets.exceptions
import json
import time
import enum
from datetime import datetime, timedelta
from dataclasses import dataclass
import queue

from typing import *


class CallbackState(enum.Enum):
    Pending = enum.auto()
    OK = enum.auto()
    TimedOut = enum.auto()
    Cancelled = enum.auto()
    ServerError = enum.auto()
    CallbackError = enum.auto()


ApiResponseCallback = Callable[[CallbackState, Optional[api_typing.S2CMessage]], None]

T = TypeVar('T')


class ApiResponseFuture:
    _state: CallbackState
    _reqid: int
    _processed_event: threading.Event
    _error: Optional[Exception]
    _default_wait_timeout: float

    def __init__(self, reqid: int, default_wait_timeout: float):
        self._state = CallbackState.Pending
        self._reqid = reqid
        self._processed_event = threading.Event()
        self._error = None
        self._default_wait_timeout = default_wait_timeout

    def _wt_mark_completed(self, new_state: CallbackState, error: Optional[Exception] = None):
        # No need for lock here. The state will change once.
        # But be careful, this will be called by the sdk thread, not the user thread
        self._error = error
        self._state = new_state
        self._processed_event.set()

    def wait(self, timeout: Optional[float] = None) -> None:
        # This will be called by the user thread
        if timeout is None:
            timeout = self._default_wait_timeout
        self._processed_event.wait(timeout)

    @property
    def state(self) -> CallbackState:
        return self._state

    @property
    def error(self) -> Optional[Exception]:
        return self._error

    @property
    def error_str(self) -> str:
        if self._error is not None:
            return str(self._error)
        elif self._state == CallbackState.Pending:
            return 'Not processed yet'
        elif self._state == CallbackState.Cancelled:
            return 'Cancelled'
        elif self._state == CallbackState.TimedOut:
            return 'Timed out'
        return ''


class CallbackStorageEntry:
    _reqid: int
    _callback: ApiResponseCallback
    _future: ApiResponseFuture
    _creation_timestamp: datetime
    _timeout: float

    def __init__(self, reqid: int, callback: ApiResponseCallback, future: ApiResponseFuture, timeout: float):
        self._reqid = reqid
        self._callback = callback
        self._future = future
        self._creation_timestamp = datetime.now()
        self._timeout = timeout


@dataclass
class PendingAPIBatchWrite:
    update_dict: Dict[int, WriteRequest]
    confirmation: api_parser.WriteConfirmation
    creation_timestamp: float


class BatchWriteContext:
    client: "ScrutinyClient"
    timeout: float
    requests: List[WriteRequest]

    def __init__(self, client: "ScrutinyClient", timeout: float):
        self.client = client
        self.timeout = timeout
        self.requests = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.client._flush_batch_write(self)
            self.client._wait_write_batch_complete(self)


class ScrutinyClient:
    RxMessageCallback = Callable[["ScrutinyClient", object], None]
    _UPDATE_SERVER_STATUS_INTERVAL = 2
    _MAX_WRITE_REQUEST_BATCH_SIZE = 20

    @dataclass
    class ThreadingEvents:
        stop_worker_thread: threading.Event
        disconnect: threading.Event
        disconnected: threading.Event
        msg_received: threading.Event

        def __init__(self):
            self.stop_worker_thread = threading.Event()
            self.disconnect = threading.Event()
            self.disconnected = threading.Event()
            self.msg_received = threading.Event()
            self.server_status_updated = threading.Event()

    _name: Optional[str]
    _server_state: ServerState
    _hostname: Optional[str]
    _port: Optional[int]
    _logger: logging.Logger
    _encoding: str
    _conn: Optional[websockets.sync.client.ClientConnection]
    _rx_message_callbacks: List[RxMessageCallback]
    _reqid: int
    _timeout: float
    _write_timeout: float
    _request_status_timer: Timer
    _require_status_update: bool
    _write_request_queue: "queue.Queue[WriteRequest]"
    _pending_api_batch_writes: Dict[str, PendingAPIBatchWrite]

    _worker_thread: Optional[threading.Thread]
    _threading_events: ThreadingEvents
    _conn_lock: threading.Lock
    _main_lock: threading.Lock

    _callback_storage: Dict[int, CallbackStorageEntry]
    _watchable_storage: Dict[str, WatchableHandle]
    _watchable_path_to_id_map: Dict[str, str]
    _server_info: Optional[ServerInfo]

    _active_batch_context: Optional[BatchWriteContext]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def __init__(self,
                 name: Optional[str] = None,
                 rx_message_callbacks: Optional[List[RxMessageCallback]] = None,
                 timeout=3,
                 write_timeout=3
                 ):
        logger_name = self.__class__.__name__
        if name is not None:
            logger_name += f"[{name}]"
        self._logger = logging.getLogger(logger_name)

        self._name = name
        self._server_state = ServerState.Disconnected
        self._hostname = None
        self._port = None
        self._encoding = 'utf8'
        self._conn = None
        self._rx_message_callbacks = [] if rx_message_callbacks is None else rx_message_callbacks
        self._worker_thread = None
        self._threading_events = self.ThreadingEvents()
        self._conn_lock = threading.Lock()
        self._main_lock = threading.Lock()
        self._reqid = 0
        self._timeout = timeout
        self._write_timeout = write_timeout
        self._request_status_timer = Timer(self._UPDATE_SERVER_STATUS_INTERVAL)
        self._require_status_update = False
        self._server_info = None
        self._write_request_queue = queue.Queue()
        self._pending_api_batch_writes = {}

        self._watchable_storage = {}
        self._watchable_path_to_id_map = {}
        self._callback_storage = {}

        self._active_batch_context = None

    def _start_worker_thread(self) -> None:
        self._threading_events.stop_worker_thread.clear()
        self._threading_events.disconnect.clear()
        started_event = threading.Event()
        self._worker_thread = threading.Thread(target=self._worker_thread_task, args=[started_event])
        self._worker_thread.start()
        started_event.wait()
        self._logger.debug('RX thread started')

    def _stop_worker_thread(self) -> None:
        if self._worker_thread is not None:
            if self._worker_thread.is_alive():
                self._threading_events.stop_worker_thread.set()
                self._worker_thread.join()
            self._worker_thread = None

    def _worker_thread_task(self, started_event: threading.Event) -> None:
        self._require_status_update = True  # Bootstrap status update loop
        started_event.set()

        self._request_status_timer.start()
        # _conn will be None after a disconnect
        while not self._threading_events.stop_worker_thread.is_set() and self._conn is not None:
            try:
                self._wt_process_next_server_status_update()

                msg = self._wt_recv(timeout=0.001)
                if msg is not None:
                    self._threading_events.msg_received.set()
                    # These callbacks are mainly for testing.
                    for callback in self._rx_message_callbacks:
                        callback(self, msg)

                    reqid: Optional[int] = msg.get('reqid', None)
                    cmd: Optional[str] = msg.get('cmd', None)

                    if cmd is None:
                        self._logger.error('Got a message without a "cmd" field')
                        self._logger.debug(msg)
                    else:
                        try:
                            self._wt_process_server_msg(cmd, msg, reqid)
                        except sdk_exceptions.BadResponseError as e:
                            self._logger.error(f"Bad response from server. {e}")
                            self._logger.debug(traceback.format_exc())

                        if reqid is not None:
                            self._wt_process_callbacks(cmd, msg, reqid)

                self._wt_check_callbacks_timeouts()

                self._wt_process_write_requests()

            except sdk_exceptions.ConnectionError as e:
                self._logger.error(f"Connection error in worker thread: {e}")
                self._wt_disconnect()    # Will set _conn to None
            except Exception as e:
                self._logger.error(f"Unhandled exception in worker thread: {e}")
                self._logger.debug(traceback.format_exc())
                self._wt_disconnect()    # Will set _conn to None

            if self._threading_events.disconnect.is_set():
                self._logger.debug(f"User required to disconnect")
                self._wt_disconnect()  # Will set _conn to None
                self._threading_events.disconnected.set()

            time.sleep(0.005)
        self._logger.debug('RX thread stopped')
        self._threading_events.stop_worker_thread.clear()

    def _wt_process_msg_inform_server_status(self, msg: api_typing.S2C.InformServerStatus, reqid: Optional[int]):
        self._request_status_timer.start()
        info = api_parser.parse_inform_server_status(msg)
        self._logger.debug('Updating server status')
        with self._main_lock:
            self._server_info = info
            self._threading_events.server_status_updated.set()

    def _wt_process_msg_watchable_update(self, msg: api_typing.S2C.WatchableUpdate, reqid: Optional[int]) -> None:
        updates = api_parser.parse_watchable_update(msg)

        for update in updates:
            with self._main_lock:
                watchable: Optional[WatchableHandle] = None
                if update.server_id in self._watchable_storage:
                    watchable = self._watchable_storage[update.server_id]

            if watchable is None:
                self._logger.error(f"Got watchable update for unknown watchable {update.server_id}")
                continue
            else:
                self._logger.debug(f"Updating value of {update.server_id}")

            watchable._update_value(update.value)

    def _wt_process_msg_inform_write_completion(self, msg: api_typing.S2C.WriteCompletion, reqid: Optional[int]) -> None:
        completion = api_parser.parse_write_completion(msg)

        if completion.request_token not in self._pending_api_batch_writes:
            return   # Maybe triggered by another client. Silently ignore.

        batch_write = self._pending_api_batch_writes[completion.request_token]
        if completion.batch_index not in batch_write.update_dict:
            self._logger.error("The server returned a write completion with an unknown batch_index")
            return

        write_request = batch_write.update_dict[completion.batch_index]
        if completion.success:
            write_request._watchable._set_last_write_datetime()
            write_request._mark_complete(True)
        else:
            write_request._mark_complete(False, "Server failed to write to the device")
        del batch_write.update_dict[completion.batch_index]

    def _wt_process_next_server_status_update(self) -> None:
        if self._request_status_timer.is_timed_out() or self._require_status_update:
            self._require_status_update = False
            self._request_status_timer.stop()
            req = self._make_request(API.Command.Client2Api.GET_SERVER_STATUS)
            self._send(req)  # No callback, we have a continuous listener

    def _wt_check_callbacks_timeouts(self) -> None:
        now = datetime.now()
        with self._main_lock:
            reqids = list(self._callback_storage.keys())

        for reqid in reqids:
            with self._main_lock:
                callback_entry: Optional[CallbackStorageEntry] = None
                if reqid in self._callback_storage:
                    callback_entry = self._callback_storage[reqid]

            if callback_entry is None:
                continue

            if now - callback_entry._creation_timestamp > timedelta(seconds=callback_entry._timeout):
                try:
                    callback_entry._callback(CallbackState.TimedOut, None)
                except (KeyboardInterrupt, sdk_exceptions.ConnectionError):
                    raise
                except Exception:
                    pass
                callback_entry._future._wt_mark_completed(CallbackState.TimedOut)

                with self._main_lock:
                    if reqid in self._callback_storage:
                        del self._callback_storage[reqid]

    def _wt_process_server_msg(self, cmd: str, msg: dict, reqid: Optional[int]) -> None:
        if cmd == API.Command.Api2Client.WATCHABLE_UPDATE:
            self._wt_process_msg_watchable_update(cast(api_typing.S2C.WatchableUpdate, msg), reqid)
        elif cmd == API.Command.Api2Client.INFORM_SERVER_STATUS:
            self._wt_process_msg_inform_server_status(cast(api_typing.S2C.InformServerStatus, msg), reqid)
        elif cmd == API.Command.Api2Client.INFORM_WRITE_COMPLETION:
            self._wt_process_msg_inform_write_completion(cast(api_typing.S2C.WriteCompletion, msg), reqid)

    def _wt_process_callbacks(self, cmd: str, msg: dict, reqid: int) -> None:
        callback_entry: Optional[CallbackStorageEntry] = None
        with self._main_lock:
            if reqid in self._callback_storage:
                callback_entry = self._callback_storage[reqid]

        if callback_entry is not None:
            error: Optional[Exception] = None

            if cmd == API.Command.Api2Client.ERROR_RESPONSE:
                error = Exception(msg.get('msg', "No error message provided"))
                self._logger.error(f"Server returned an error response. reqid={reqid}. {error}")

                try:
                    callback_entry._callback(CallbackState.ServerError, msg)
                except (KeyboardInterrupt, sdk_exceptions.ConnectionError):
                    raise
                except Exception:
                    pass
                finally:
                    callback_entry._future._wt_mark_completed(CallbackState.ServerError, error=error)
            else:
                try:
                    self._logger.debug(f"Running {cmd} callback for request ID {reqid}")
                    callback_entry._callback(CallbackState.OK, msg)
                except (KeyboardInterrupt, sdk_exceptions.ConnectionError):
                    raise
                except Exception as e:
                    error = e

                if error is not None:
                    self._logger.error(f"Callback raised an exception. cmd={cmd}, reqid={reqid}. {error}")
                    self._logger.debug(traceback.format_exc())
                    callback_entry._future._wt_mark_completed(CallbackState.CallbackError, error=error)

                elif callback_entry._future.state == CallbackState.Pending:
                    callback_entry._future._wt_mark_completed(CallbackState.OK)

            with self._main_lock:
                if reqid in self._callback_storage:
                    del self._callback_storage[reqid]

    def _wt_process_write_requests(self) -> None:
        # Note _pending_api_batch_writes is always accessed from worker thread
        api_req = self._make_request(API.Command.Client2Api.WRITE_VALUE, {'updates': []})
        api_req = cast(api_typing.C2S.WriteValue, api_req)

        # Clear old requests.
        # No need for lock here. The _request_queue crosses time domain boundaries
        now = time.time()
        if len(self._pending_api_batch_writes) > 0:
            tokens = list(self._pending_api_batch_writes.keys())
            for token in tokens:
                pending_batch = self._pending_api_batch_writes[token]
                if now - pending_batch.creation_timestamp > self._write_timeout:
                    for request in pending_batch.update_dict.values():  # Completed request are already removed of that dict.
                        request._mark_complete(False, "Timed out")
                    del self._pending_api_batch_writes[token]

                # Once a batch is fully processed, meaning all requests have been treated and removed
                # We can prune the remaining empty batch
                if len(pending_batch.update_dict) == 0:
                    del self._pending_api_batch_writes[token]

        # Process new requests
        n = 0
        batch_dict: Dict[int, WriteRequest] = {}
        while not self._write_request_queue.empty():
            request = self._write_request_queue.get()
            assert request._watchable._server_id is not None
            api_req['updates'].append({
                'batch_index': n,
                'watchable': request._watchable._server_id,
                'value': request._value
            })
            batch_dict[n] = request
            n += 1

            if n >= self._MAX_WRITE_REQUEST_BATCH_SIZE:
                break

        if len(api_req['updates']) == 0:
            return

        def _wt_write_response_callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK:
                confirmation = api_parser.parse_write_value_response(cast(api_typing.S2C.WriteValue, response))

                if confirmation.count != len(batch_dict):
                    request._mark_complete(False, f"Count mismatch in request and server confirmation.")
                else:
                    self._pending_api_batch_writes[confirmation.request_token] = PendingAPIBatchWrite(
                        update_dict=batch_dict,
                        confirmation=confirmation,
                        creation_timestamp=time.time()
                    )
            else:
                request._mark_complete(False, state.name)

        self._send(api_req, _wt_write_response_callback)
        # We don't need the future object here because the WriteRequest act as one.

    def _wt_disconnect(self) -> None:
        """Disconnect from a Scrutiny server, called by the Worker Thread .
            Does not throw an exception in case of broken pipe
        """

        with self._conn_lock:
            if self._conn is not None:
                self._logger.info(f"Disconnecting from server at {self._hostname}:{self._port}")
                try:
                    self._conn.close()
                except (websockets.exceptions.WebSocketException, socket.error):
                    self._logger.debug("Failed to close the websocket")
                    self._logger.debug(traceback.format_exc())

            self._conn = None

        with self._main_lock:
            self._hostname = None
            self._port = None
            self._server_state = ServerState.Disconnected
            self._server_info = None

            for watchable in self._watchable_storage.values():
                watchable._set_invalid(ValueStatus.ServerGone)
            self._watchable_storage.clear()
            self._watchable_path_to_id_map.clear()

            for callback_entry in self._callback_storage.values():
                if callback_entry._future.state == CallbackState.Pending:
                    callback_entry._future._wt_mark_completed(CallbackState.Cancelled)
            self._callback_storage.clear()

    def _register_callback(self, reqid: int, callback: ApiResponseCallback, timeout: float) -> ApiResponseFuture:
        future = ApiResponseFuture(reqid, default_wait_timeout=timeout + 0.5)    # Allow some margin for thread to mark it timed out
        callback_entry = CallbackStorageEntry(
            reqid=reqid,
            callback=callback,
            future=future,
            timeout=timeout
        )

        with self._main_lock:
            self._callback_storage[reqid] = callback_entry
        return future

    def _send(self,
              obj: api_typing.C2SMessage,
              callback: Optional[ApiResponseCallback] = None,
              timeout: Optional[float] = None
              ) -> Optional[ApiResponseFuture]:
        """Sends a message to the API"""

        error: Optional[Exception] = None
        future: Optional[ApiResponseFuture] = None

        if timeout is None:
            timeout = self._timeout

        if not isinstance(obj, dict):
            raise TypeError(f'ScrutinyClient only sends data under the form of a dictionary. Received {obj.__class__.__name__}')

        if callback is not None:
            if 'reqid' not in obj:
                raise RuntimeError("Missing reqid in request")

            future = self._register_callback(obj['reqid'], callback, timeout=timeout)

        with self._conn_lock:
            if self._conn is None:
                raise sdk_exceptions.ConnectionError(f"Disconnected from server")

            try:
                s = json.dumps(obj)
                self._logger.debug(f"Sending {s}")
                self._conn.send(s.encode(self._encoding))
            except TimeoutError:
                pass
            except (websockets.exceptions.WebSocketException, socket.error) as e:
                error = e
                self._logger.debug(traceback.format_exc())

        if error:
            self.disconnect()
            raise sdk_exceptions.ConnectionError(f"Disconnected from server. {error}")

        return future

    def _wt_recv(self, timeout: Optional[float] = None) -> Optional[dict]:
        # No need to lock conn_lock here. Important is during disconnection
        error: Optional[Exception] = None
        obj: Optional[dict] = None

        if self._conn is None:
            raise sdk_exceptions.ConnectionError(f"Disconnected from server")

        try:
            data = self._conn.recv(timeout=timeout)
            if isinstance(data, bytes):
                data = data.decode(self._encoding)
            self._logger.debug(f"Received {data}")
            obj = json.loads(data)
        except TimeoutError:
            pass
        except (websockets.exceptions.WebSocketException, socket.error) as e:
            error = e
            self._logger.debug(traceback.format_exc())

        if error:
            self._wt_disconnect()
            raise sdk_exceptions.ConnectionError(f"Disconnected from server. {error}")

        return obj

    def _make_request(self, command: str, data: Optional[dict] = None) -> api_typing.C2SMessage:
        with self._main_lock:
            reqid = self._reqid
            self._reqid += 1
            if self._reqid >= 2**32 - 1:
                self._reqid = 0

        cmd: api_typing.BaseC2SMessage = {
            'cmd': command,
            'reqid': reqid
        }

        if data is None:
            data = {}
        cmd.update(data)    # type: ignore

        return cmd

    def _enqueue_write_request(self, request: WriteRequest):
        self._write_request_queue.put(request)

    def __del__(self):
        self.disconnect()

    def _is_batch_write_in_progress(self) -> bool:
        return self._active_batch_context is not None

    def _process_write_request(self, request: WriteRequest):
        if self._is_batch_write_in_progress():
            assert self._active_batch_context is not None
            self._active_batch_context.requests.append(request)
        else:
            self._enqueue_write_request(request)

    def _flush_batch_write(self, batch_write_context: BatchWriteContext) -> None:
        for request in batch_write_context.requests:
            self._enqueue_write_request(request)

    def _wait_write_batch_complete(self, batch: BatchWriteContext) -> None:
        tstart = time.time()

        incomplete_count: Optional[int] = None
        try:
            for write_request in batch.requests:
                remaining_time = max(0, batch.timeout - (time.time() - tstart))
                write_request.wait_for_completion(timeout=remaining_time)
            timed_out = False
        except sdk_exceptions.TimeoutException:
            timed_out = True

        if timed_out:
            incomplete_count = 0
            for request in batch.requests:
                if not request.completed:
                    incomplete_count += 1

            if incomplete_count > 0:
                raise sdk_exceptions.TimeoutException(
                    f"Incomplete batch write. {incomplete_count} write requests not completed in {batch.timeout} sec. ")

    # === User API ====

    def connect(self, hostname: str, port: int, **kwargs) -> "ScrutinyClient":
        """Connect to a Scrutiny server through a websocket.

        :param hostname: The hostname or ip address of the server
        :param port: The listening port of the server

        :raises ``scrutiny.sdk.exceptions.ConnectionError``: In case of failure
        """
        self.disconnect()

        with self._main_lock:
            self._hostname = hostname
            self._port = port
            uri = f'ws://{self._hostname}:{self._port}'
            connect_error: Optional[Exception] = None
            self._logger.info(f"Connecting to {uri}")
            with self._conn_lock:
                try:
                    self._server_state = ServerState.Connecting
                    self._conn = websockets.sync.client.connect(uri, **kwargs)
                    self._server_state = ServerState.Connected
                    self._start_worker_thread()
                except (websockets.exceptions.WebSocketException, socket.error) as e:
                    self._logger.debug(traceback.format_exc())
                    connect_error = e

        if connect_error is not None:
            self.disconnect()
            raise sdk_exceptions.ConnectionError(f'Failed to connect to the server at "{uri}". Error: {connect_error}')

        return self

    def disconnect(self) -> None:
        if self._worker_thread is None:
            self._wt_disconnect()  # Can call safely from this thread
            return

        if not self._worker_thread.is_alive():
            self._wt_disconnect()  # Can call safely from this thread
            return

        self._threading_events.disconnected.clear()
        self._threading_events.disconnect.set()
        self._threading_events.disconnected.wait(timeout=2)  # Timeout avoid race condition if the thread was exiting

        self._stop_worker_thread()

    def watch(self, path: str, pause=False) -> WatchableHandle:
        if not isinstance(path, str):
            raise ValueError("Path must be a string")

        if '*' in path:
            raise ValueError("Glob wildcards are not allowed")

        cached_watchable: Optional[WatchableHandle] = None
        with self._main_lock:
            if path in self._watchable_path_to_id_map:
                server_id = self._watchable_path_to_id_map[path]
                if server_id in self._watchable_storage:
                    cached_watchable = self._watchable_storage[path]

        if cached_watchable is not None:
            return cached_watchable

        watchable = WatchableHandle(self, path)
        req = self._make_request(API.Command.Client2Api.GET_WATCHABLE_LIST, {
            'max_per_response': 2,
            'filter': {'name': path}
        })

        # The watchable will be written by this callback from the worker thread. The watchable object is thread-safe.
        def wt_get_watchable_callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK:
                response = cast(api_typing.S2C.GetWatchableList, response)
                parsed_content = api_parser.parse_get_watchable_single_element(response, path)

                watchable._configure(
                    watchable_type=parsed_content.watchable_type,
                    datatype=parsed_content.datatype,
                    server_id=parsed_content.server_id
                )

        future = self._send(req, wt_get_watchable_callback)
        assert future is not None
        future.wait()

        if future.state != CallbackState.OK:
            raise sdk_exceptions.OperationFailure(f"Failed to get the watchable definition. {future.error_str}")

        def wt_subscribe_callback(state: CallbackState, response: Optional[api_typing.S2CMessage]):
            if response is not None and state == CallbackState.OK:
                response = cast(api_typing.S2C.SubscribeWatchable, response)
                if len(response['watchables']) != 1:
                    raise sdk_exceptions.BadResponseError(
                        f'The server did confirmed the subscription of {len(response["watchables"])} while we requested only for 1')

                if response['watchables'][0] != watchable._server_id:
                    raise sdk_exceptions.BadResponseError(
                        f'The server did not confirm the subscription for the right watchable. Got {response["watchables"][0]}, expected {watchable._server_id}')

        req = self._make_request(API.Command.Client2Api.SUBSCRIBE_WATCHABLE, {
            'watchables': [
                watchable._server_id
            ]
        })
        future = self._send(req, wt_subscribe_callback)
        assert future is not None
        future.wait()

        if future.state != CallbackState.OK:
            raise sdk_exceptions.OperationFailure(f"Failed to subscribe to the watchable. {future.error_str}")

        assert watchable._server_id is not None
        with self._main_lock:
            self._watchable_path_to_id_map[watchable.display_path] = watchable._server_id
            self._watchable_storage[watchable._server_id] = watchable

        return watchable

    def wait_new_value_for_all(self, timeout: int = 5) -> None:
        counter_map: Dict[str, Optional[int]] = {}
        with self._main_lock:
            watchable_storage_copy = self._watchable_storage.copy()  # Shallow copy

        for server_id in watchable_storage_copy:
            counter_map[server_id] = watchable_storage_copy[server_id]._update_counter

        tstart = time.time()
        for server_id in watchable_storage_copy:
            timeout_remainder = max(round(timeout - (time.time() - tstart), 2), 0)
            # Wait update will throw if the server has gone away as the _disconnect method will set all watchables "invalid"
            watchable_storage_copy[server_id].wait_update(previous_counter=counter_map[server_id], timeout=timeout_remainder)

    def wait_server_status_update(self, timeout: float = _UPDATE_SERVER_STATUS_INTERVAL + 0.5):
        self._threading_events.server_status_updated.clear()
        self._threading_events.server_status_updated.wait(timeout=timeout)

        if not self._threading_events.server_status_updated.is_set():
            raise sdk_exceptions.TimeoutException(f"Server status did not update within a {timeout} seconds delay")

    def batch_write(self, timeout: Optional[float] = None) -> BatchWriteContext:
        if self._active_batch_context is not None:
            raise sdk_exceptions.OperationFailure("Batch write cannot be nested")

        if timeout is None:
            timeout = self._write_timeout

        batch_context = BatchWriteContext(self, timeout)
        self._active_batch_context = batch_context
        return batch_context

    @property
    def name(self) -> str:
        return '' if self._name is None else self.name

    @property
    def server_state(self) -> ServerState:
        with self._main_lock:
            val = self._server_state  # Can be modified by the worker_thread
        return val

    @property
    def server(self) -> Optional[ServerInfo]:
        # server_info is readonly and only it,s reference gets changed when updated.
        # We can safely return a reference here. The user can't mess it up
        with self._main_lock:
            info = self._server_info
        return info

    @property
    def hostname(self) -> Optional[str]:
        with self._main_lock:
            val = self._hostname  # Can be modified by the worker_thread
        return val

    @property
    def port(self) -> Optional[int]:
        with self._main_lock:
            val = self._port  # Can be modified by the worker_thread
        return val
