__all__ = ['Client']


from scrutiny.sdk.definitions import *
from scrutiny.sdk.watchable_handle import WatchableHandle
import scrutiny.sdk.exceptions as sdk_exceptions
from scrutiny.core.basic_types import *
from scrutiny.tools.timer import Timer

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

from typing import *


class CallbackState(enum.Enum):
    Pending = enum.auto()
    OK = enum.auto()
    TimedOut = enum.auto()
    Cancelled = enum.auto()
    ServerError = enum.auto()
    CallbackError = enum.auto()


ApiResponseCallback = Callable[[CallbackState, Optional[api_typing.S2CMessage]], None]


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

    def _mark_completed(self, new_state: CallbackState, error: Optional[Exception] = None):
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


class ScrutinyClient:
    RxMessageCallback = Callable[["ScrutinyClient", object], None]
    _UPDATE_SERVER_STATUS_INTERVAL = 2

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

    _name: Optional[str]
    _server_state: ServerState
    _device_link_state: DeviceLinkState
    _hostname: Optional[str]
    _port: Optional[int]
    _logger: logging.Logger
    _encoding: str
    _conn: Optional[websockets.sync.client.ClientConnection]
    _rx_message_callbacks: List[RxMessageCallback]
    _reqid: int
    _timeout: float
    _request_status_timer: Timer

    _worker_thread: Optional[threading.Thread]
    _threading_events: ThreadingEvents
    _conn_lock: threading.Lock
    _main_lock: threading.Lock

    _callback_storage: Dict[int, CallbackStorageEntry]
    _watchable_storage: Dict[str, WatchableHandle]

    def __init__(self,
                 name: Optional[str] = None,
                 rx_message_callbacks: Optional[List[RxMessageCallback]] = None,
                 timeout=3
                 ):
        logger_name = self.__class__.__name__
        if name is not None:
            logger_name += f"[{name}]"
        self._logger = logging.getLogger(logger_name)

        self._name = name
        self._server_state = ServerState.Disconnected
        self._device_link_state = DeviceLinkState.NA
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
        self._request_status_timer = Timer(self._UPDATE_SERVER_STATUS_INTERVAL)

        self._watchable_storage = {}
        self._callback_storage = {}

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
        started_event.set()

        self._request_status_timer.start()
        # _conn will be None after a disconnect
        while not self._threading_events.stop_worker_thread.is_set() and self._conn is not None:
            try:
                self._wt_process_next_server_status_update()
                if self._request_status_timer.is_timed_out():
                    # self._send()   todo
                    self._request_status_timer.start()

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
                        self._wt_process_server_msg(cmd, msg, reqid)

                        if reqid is not None:
                            self._wt_process_callbacks(cmd, msg, reqid)

                self._wt_check_callbacks_timeouts()

            except sdk_exceptions.ConnectionError as e:
                self._logger.error(f"Connection error in worker thread: {e}")
                self._wt_disconnect()    # Will set _conn to None
            except Exception as e:
                self._logger.error(f"Unhandled exception in worker thread: {e}")
                self._wt_disconnect()    # Will set _conn to None

            if self._threading_events.disconnect.is_set():
                self._logger.debug(f"User required to disconnect")
                self._wt_disconnect()  # Will set _conn to None
                self._threading_events.disconnected.set()

            time.sleep(0.005)
        self._logger.debug('RX thread stopped')
        self._threading_events.stop_worker_thread.clear()

    def _wt_process_inform_server_status(self, msg: api_typing.S2C.InformServerStatus, reqid: Optional[int]):
        print(msg)
        self._request_status_timer.start()

    def _wt_process_next_server_status_update(self) -> None:
        if self._request_status_timer.is_stopped():
            self._request_status_timer.start()

        if self._request_status_timer.is_timed_out():
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
                callback_entry._future._mark_completed(CallbackState.TimedOut)

                with self._main_lock:
                    if reqid in self._callback_storage:
                        del self._callback_storage[reqid]

    def _wt_process_server_msg(self, cmd: str, msg: dict, reqid: Optional[int]) -> None:
        if cmd == API.Command.Api2Client.INFORM_SERVER_STATUS:
            self._wt_process_inform_server_status(cast(api_typing.S2C.InformServerStatus, msg), reqid)

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
                    callback_entry._future._mark_completed(CallbackState.ServerError, error=error)
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
                    callback_entry._future._mark_completed(CallbackState.CallbackError, error=error)

                elif callback_entry._future.state == CallbackState.Pending:
                    callback_entry._future._mark_completed(CallbackState.OK)

            with self._main_lock:
                if reqid in self._callback_storage:
                    del self._callback_storage[reqid]

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
            self._device_link_state = DeviceLinkState.NA

            for watchable in self._watchable_storage.values():
                watchable._set_invalid(ValueStatus.ServerGone)
            self._watchable_storage.clear()

            for callback_entry in self._callback_storage.values():
                if callback_entry._future.state == CallbackState.Pending:
                    callback_entry._future._mark_completed(CallbackState.Cancelled)
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
                data = json.dumps(obj).encode(self._encoding)
                self._conn.send(data)
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

    def __del__(self):
        self.disconnect()

    # === User API ====

    def connect(self, hostname: str, port: int, **kwargs) -> None:
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
            if path in self._watchable_storage:
                cached_watchable = self._watchable_storage[path]

        if cached_watchable is not None:
            return cached_watchable

        watchable = WatchableHandle(self, path)
        req = self._make_request(API.Command.Client2Api.GET_WATCHABLE_LIST, {
            'max_per_response': 2,
            'filter': {
                'name': path
            }
        })

        # The watchable will be written by this callback from the worker thread. The watchable object is thread-safe.
        def wt_get_watchable_callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK:
                response = cast(api_typing.S2C.GetWatchableList, response)
                total = response['qty']['alias'] + response['qty']['rpv'] + response['qty']['var']
                if total == 0:
                    raise sdk_exceptions.NameNotFoundError(f'No watchable element matches the path {path} on the server')

                if total > 1:
                    raise sdk_exceptions.BadResponseError(f"More than one item were returned by the server that matched the path {path}")

                watchable_type: WatchableType = WatchableType.NA
                content: Any = None
                if response['qty']['alias'] == 1:
                    watchable_type = WatchableType.Alias
                    content = response.get('content', {}).get('alias', None)
                elif response['qty']['rpv']:
                    watchable_type = WatchableType.RuntimePulishedValue
                    content = response.get('content', {}).get('rpv', None)
                elif response['qty']['var']:
                    watchable_type = WatchableType.Variable
                    content = response.get('content', {}).get('var', None)
                else:
                    raise sdk_exceptions.BadResponseError('Unknown watchable type')

                if content is None or not isinstance(content, list):
                    raise sdk_exceptions.BadResponseError("Missing watchable definition in API response")

                if len(content) != 1:
                    raise sdk_exceptions.BadResponseError("Incoherent element quantity in API response.")

                content = cast(dict, content[0])

                required_fields = ['id', 'display_path', 'datatype']
                for field in required_fields:
                    if field not in content:
                        raise sdk_exceptions.BadResponseError(f"Missing field {field} in watchable definition")

                if content['datatype'] not in API.APISTR_2_DATATYPE:
                    raise RuntimeError(f"Unknown datatype {content['datatype']}")

                datatype = EmbeddedDataType(API.APISTR_2_DATATYPE[content['datatype']])

                if path != content['display_path']:
                    raise sdk_exceptions.BadResponseError(
                        f"The display path of the element returned by the server does not matched the requested path. Got {content['display_path']} but expected {path}")

                watchable._configure(
                    watchable_type=watchable_type,
                    datatype=datatype,
                    server_id=content['id']
                )

        future = self._send(req, wt_get_watchable_callback)
        assert future is not None
        future.wait()

        if future.state != CallbackState.OK:
            raise sdk_exceptions.OperationFailure(f"Failed to get the watchable definition. {future.error_str}")

        with self._main_lock:
            self._watchable_storage[watchable.display_path] = watchable

        return watchable

    def wait_new_value_for_all(self, timeout: int = 5) -> None:
        timestamp_map: Dict[str, Optional[datetime]] = {}
        with self._main_lock:
            watchable_storage_copy = self._watchable_storage.copy()  # Shallow copy

        for display_path in watchable_storage_copy:
            timestamp_map[display_path] = watchable_storage_copy[display_path].last_update_timestamp

        tstart = time.time()
        for display_path in watchable_storage_copy:
            timeout_remainder = max(round(timeout - (time.time() - tstart), 2), 0)
            # Wait update will throw if the server has gone away as the _disconnect method will set all watchables "invalid"
            watchable_storage_copy[display_path].wait_update(since_timestamp=timestamp_map[display_path], timeout=timeout_remainder)

    @property
    def name(self) -> str:
        return '' if self._name is None else self.name

    @property
    def server_state(self) -> ServerState:
        with self._main_lock:
            val = self._server_state  # Can be modified by the worker_thread
        return val

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
