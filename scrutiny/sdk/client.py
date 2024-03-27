#    client.py
#        A client that can talk with the Scrutiny server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['Client']


import scrutiny.sdk
import scrutiny.sdk.datalogging
from scrutiny.core import validation
sdk = scrutiny.sdk
from scrutiny.sdk import _api_parser as api_parser
from scrutiny.sdk.definitions import *
from scrutiny.sdk.watchable_handle import WatchableHandle
from scrutiny.core.basic_types import *
from scrutiny.tools.timer import Timer
from scrutiny.sdk.write_request import WriteRequest
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
from base64 import b64encode
import queue
import types

from typing import List, Dict, Optional, Callable, cast, Union, TypeVar, Tuple, Type, Any, Literal


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

    def __init__(self, reqid: int, default_wait_timeout: float) -> None:
        self._state = CallbackState.Pending
        self._reqid = reqid
        self._processed_event = threading.Event()
        self._error = None
        self._default_wait_timeout = default_wait_timeout

    def _wt_mark_completed(self, new_state: CallbackState, error: Optional[Exception] = None) -> None:
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
    timeout: float


class BatchWriteContext:
    client: "ScrutinyClient"
    timeout: float
    requests: List[WriteRequest]

    def __init__(self, client: "ScrutinyClient", timeout: float) -> None:
        self.client = client
        self.timeout = timeout
        self.requests = []

    def __enter__(self) -> "BatchWriteContext":
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[types.TracebackType]) -> Literal[False]:
        if exc_type is None:
            self.client._flush_batch_write(self)
            try:
                self.client._wait_write_batch_complete(self)
            finally:
                self.client._end_batch()
        self.client._end_batch()
        return False


class FlushPoint:
    pass


class ScrutinyClient:
    RxMessageCallback = Callable[["ScrutinyClient", object], None]
    _UPDATE_SERVER_STATUS_INTERVAL = 2
    _MAX_WRITE_REQUEST_BATCH_SIZE = 500
    _MEMORY_READ_DATA_LIFETIME = 30
    _MEMORY_WRITE_DATA_LIFETIME = 30

    @dataclass
    class ThreadingEvents:
        stop_worker_thread: threading.Event
        disconnect: threading.Event
        disconnected: threading.Event
        msg_received: threading.Event
        sync_complete: threading.Event
        require_sync: threading.Event

        def __init__(self) -> None:
            self.stop_worker_thread = threading.Event()
            self.disconnect = threading.Event()
            self.disconnected = threading.Event()
            self.msg_received = threading.Event()
            self.server_status_updated = threading.Event()
            self.sync_complete = threading.Event()
            self.require_sync = threading.Event()

    _name: Optional[str]        # Name of the client instance
    _server_state: ServerState  # State of the communication with the server. Connected/disconnected/connecting, etc
    _hostname: Optional[str]    # Hostname of the server
    _port: Optional[int]        # Port number of the server
    _logger: logging.Logger     # logging interface
    _encoding: str              # The API string encoding. utf-8
    _conn: Optional[websockets.sync.client.ClientConnection]    # The websocket handles to the server
    _rx_message_callbacks: List[RxMessageCallback]  # List of callbacks to call for each message received. (mainly for testing)
    _reqid: int                 # The actual request ID. Increasing integer
    _timeout: float             # Default timeout value for server requests
    _write_timeout: float       # Default timeout value for write request
    _request_status_timer: Timer    # Timer for periodic server status update
    _require_status_update: bool    # boolean indicating that a new server status request should be sent
    _write_request_queue: "queue.Queue[Union[WriteRequest, FlushPoint, BatchWriteContext]]"  # Queue of write request given by the users.

    _pending_api_batch_writes: Dict[str, PendingAPIBatchWrite]  # Dict of all the pending batch write currently in progress,
    # indexed by the request token
    # Dict of all the pending memory read requests, index by their request_token
    _memory_read_completion_dict: Dict[str, api_parser.MemoryReadCompletion]
    # Dict of all the pending memory write requests, index by their request_token
    _memory_write_completion_dict: Dict[str, api_parser.MemoryWriteCompletion]
    # Dict of all the datalogging requests, index by their request_token
    _pending_datalogging_requests: Dict[str, sdk.datalogging.DataloggingRequest]

    _worker_thread: Optional[threading.Thread]  # The thread that handles the communication
    _threading_events: ThreadingEvents  # All the threading events grouped under a single object
    _conn_lock: threading.Lock  # A threading lock to access the websocket
    _main_lock: threading.Lock  # A threading lock to access the client internal state variables

    _callback_storage: Dict[int, CallbackStorageEntry]  # Dict of all pending server request index by their request ID
    _watchable_storage: Dict[str, WatchableHandle]  # A cache of all the WatchableHandle given to the user, index by their display path
    _watchable_path_to_id_map: Dict[str, str]   # A dict that maps the watchables from display path to their server id
    _server_info: Optional[ServerInfo]  # The actual server internal state given by inform_server_status

    _active_batch_context: Optional[BatchWriteContext]  # The active write batch. All writes are appended to it if not None
    _last_device_session_id: Optional[str]  # The last device session ID observed. Used to detect disconnection/reconnection
    _last_sfd_firmware_id: Optional[str]    # The last loaded SFD seen. Used to detect change in SFD

    def __enter__(self) -> "ScrutinyClient":
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[types.TracebackType]) -> Literal[False]:
        self.disconnect()
        return False

    def __init__(self,
                 name: Optional[str] = None,
                 rx_message_callbacks: Optional[List[RxMessageCallback]] = None,
                 timeout: float = 4.0,
                 write_timeout: float = 5.0
                 ):
        """ 
            Creates a client that can communicate with a Scrutiny server

            :param name: Name of the client. Used for logging
            :param rx_message_callbacks: A callback to call each time a server message is received. Called from a separate thread. Mainly used for debugging and testing
            :param timeout: Default timeout to use when making a request to the server
            :param write_timeout: Default timeout to use when writing to the device memory
        """
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
        self._memory_read_completion_dict = {}
        self._memory_write_completion_dict = {}
        self._pending_datalogging_requests = {}

        self._watchable_storage = {}
        self._watchable_path_to_id_map = {}
        self._callback_storage = {}
        self._last_device_session_id = None
        self._last_sfd_firmware_id = None

        self._active_batch_context = None

    def _start_worker_thread(self) -> None:
        self._threading_events.stop_worker_thread.clear()
        self._threading_events.disconnect.clear()
        started_event = threading.Event()
        self._worker_thread = threading.Thread(target=self._worker_thread_task, args=[started_event], daemon=True)
        self._worker_thread.start()
        started_event.wait()
        self._logger.debug('Worker thread started')

    def _stop_worker_thread(self) -> None:
        if self._worker_thread is not None:
            self._logger.debug("Stopping worker thread")
            if self._worker_thread.is_alive():
                self._threading_events.stop_worker_thread.set()
                self._worker_thread.join()
                self._logger.debug("Worker thread stopped")
            else:
                self._logger.debug("Worker thread already stopped")
            self._worker_thread = None

    def _worker_thread_task(self, started_event: threading.Event) -> None:
        self._require_status_update = True  # Bootstrap status update loop
        started_event.set()

        self._request_status_timer.start()
        # _conn will be None after a disconnect
        while not self._threading_events.stop_worker_thread.is_set() and self._conn is not None:
            require_sync_before = False
            try:
                if self._threading_events.require_sync.is_set():
                    require_sync_before = True

                self._wt_process_next_server_status_update()

                msg = self._wt_recv(timeout=0.001)
                if msg is not None:
                    self.wt_process_rx_api_message(msg)

                self._wt_check_callbacks_timeouts()
                self._check_deferred_response_timeouts()
                self._wt_process_write_watchable_requests()
                self._wt_process_device_state()

            except sdk.exceptions.ConnectionError as e:
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

            if require_sync_before:
                self._threading_events.require_sync.clear()
                self._threading_events.sync_complete.set()

            time.sleep(0.005)
        self._logger.debug('Worker thread is exiting')
        self._threading_events.stop_worker_thread.clear()

    def _wt_process_msg_inform_server_status(self, msg: api_typing.S2C.InformServerStatus, reqid: Optional[int]) -> None:
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
                self._logger.debug(f"Updating value of {update.server_id} ({watchable.name})")

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

    def _wt_process_msg_inform_memory_read_complete(self, msg: api_typing.S2C.ReadMemoryComplete, reqid: Optional[int]) -> None:
        completion = api_parser.parse_memory_read_completion(msg)
        with self._main_lock:
            if completion.request_token not in self._memory_read_completion_dict:
                self._memory_read_completion_dict[completion.request_token] = completion
            else:
                self._logger.error(f"Received duplicate memory read completion with request token {completion.request_token}")

    def _wt_process_msg_inform_memory_write_complete(self, msg: api_typing.S2C.WriteMemoryComplete, reqid: Optional[int]) -> None:
        completion = api_parser.parse_memory_write_completion(msg)
        with self._main_lock:
            if completion.request_token not in self._memory_write_completion_dict:
                self._memory_write_completion_dict[completion.request_token] = completion
            else:
                self._logger.error(f"Received duplicate memory write completion with request token {completion.request_token}")

    def _wt_process_msg_datalogging_acquisition_complete(self, msg: api_typing.S2C.InformDataloggingAcquisitionComplete, reqid: Optional[int]) -> None:
        completion = api_parser.parse_datalogging_acquisition_complete(msg)
        if completion.request_token not in self._pending_datalogging_requests:
            self._logger.warning('Received a notice of completion for a datalogging acquisition, but its request_token was unknown')
            return

        request = self._pending_datalogging_requests[completion.request_token]
        request._mark_complete(completion.success, completion.reference_id, completion.detail_msg)
        del self._pending_datalogging_requests[completion.request_token]

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
                except (sdk.exceptions.ConnectionError):
                    raise
                except Exception:
                    pass
                callback_entry._future._wt_mark_completed(CallbackState.TimedOut)

                with self._main_lock:
                    if reqid in self._callback_storage:
                        del self._callback_storage[reqid]

    def _check_deferred_response_timeouts(self) -> None:
        with self._main_lock:
            keys = list(self._memory_read_completion_dict.keys())
            for k in keys:
                if time.time() - self._memory_read_completion_dict[k].timestamp > self._MEMORY_READ_DATA_LIFETIME:
                    del self._memory_read_completion_dict[k]

            keys = list(self._memory_write_completion_dict.keys())
            for k in keys:
                if time.time() - self._memory_write_completion_dict[k].timestamp > self._MEMORY_WRITE_DATA_LIFETIME:
                    del self._memory_write_completion_dict[k]

    def wt_process_rx_api_message(self, msg: Dict[str, Any]) -> None:
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
                if cmd == API.Command.Api2Client.WATCHABLE_UPDATE:
                    self._wt_process_msg_watchable_update(cast(api_typing.S2C.WatchableUpdate, msg), reqid)
                elif cmd == API.Command.Api2Client.INFORM_SERVER_STATUS:
                    self._wt_process_msg_inform_server_status(cast(api_typing.S2C.InformServerStatus, msg), reqid)
                elif cmd == API.Command.Api2Client.INFORM_WRITE_COMPLETION:
                    self._wt_process_msg_inform_write_completion(cast(api_typing.S2C.WriteCompletion, msg), reqid)
                elif cmd == API.Command.Api2Client.INFORM_MEMORY_READ_COMPLETE:
                    self._wt_process_msg_inform_memory_read_complete(cast(api_typing.S2C.ReadMemoryComplete, msg), reqid)
                elif cmd == API.Command.Api2Client.INFORM_MEMORY_WRITE_COMPLETE:
                    self._wt_process_msg_inform_memory_write_complete(cast(api_typing.S2C.WriteMemoryComplete, msg), reqid)
                elif cmd == API.Command.Api2Client.INFORM_DATALOGGING_ACQUISITION_COMPLETE:
                    self._wt_process_msg_datalogging_acquisition_complete(cast(api_typing.S2C.InformDataloggingAcquisitionComplete, msg), reqid)
            except sdk.exceptions.BadResponseError as e:
                self._logger.error(f"Bad message from server. {e}")
                self._logger.debug(traceback.format_exc())

            if reqid is not None:   # message is a response to a request
                self._wt_process_callbacks(cmd, msg, reqid)

    def _wt_process_callbacks(self, cmd: str, msg: Dict[str, Any], reqid: int) -> None:
        callback_entry: Optional[CallbackStorageEntry] = None
        with self._main_lock:
            if reqid in self._callback_storage:
                callback_entry = self._callback_storage[reqid]

        # We have a callback for that response
        if callback_entry is not None:
            error: Optional[Exception] = None

            if cmd == API.Command.Api2Client.ERROR_RESPONSE:
                error = Exception(msg.get('msg', "No error message provided"))
                self._logger.error(f"Server returned an error response. reqid={reqid}. {error}")

                try:
                    callback_entry._callback(CallbackState.ServerError, msg)
                except (sdk.exceptions.ConnectionError):
                    raise
                except Exception:
                    pass
                finally:
                    callback_entry._future._wt_mark_completed(CallbackState.ServerError, error=error)
            else:
                try:
                    self._logger.debug(f"Running {cmd} callback for request ID {reqid}")
                    callback_entry._callback(CallbackState.OK, msg)
                except (sdk.exceptions.ConnectionError):
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

    def _wt_process_write_watchable_requests(self) -> None:
        # Note _pending_api_batch_writes is always accessed from worker thread
        api_req = self._make_request(API.Command.Client2Api.WRITE_WATCHABLE, {'updates': []})
        api_req = cast(api_typing.C2S.WriteValue, api_req)

        # Clear old requests.
        # No need for lock here. The _request_queue crosses time domain boundaries
        now = time.time()
        if len(self._pending_api_batch_writes) > 0:
            tokens = list(self._pending_api_batch_writes.keys())
            for token in tokens:
                pending_batch = self._pending_api_batch_writes[token]
                if now - pending_batch.creation_timestamp > pending_batch.timeout:
                    for request in pending_batch.update_dict.values():  # Completed request are already removed of that dict.
                        request._mark_complete(False, f"Timed out ({pending_batch.timeout} seconds)")
                    del self._pending_api_batch_writes[token]
                else:
                    for request in pending_batch.update_dict.values():  # Completed request are already removed of that dict.
                        if request.watchable._is_dead():
                            request._mark_complete(False, f"{request.watchable.name} is not available anymore")

                # Once a batch is fully processed, meaning all requests have been treated and removed
                # We can prune the remaining empty batch
                if len(pending_batch.update_dict) == 0:
                    del self._pending_api_batch_writes[token]

        # Process new requests
        n = 0
        batch_dict: Dict[int, WriteRequest] = {}
        while not self._write_request_queue.empty():
            obj = self._write_request_queue.get()
            if isinstance(obj, FlushPoint):
                break
            requests: List[WriteRequest] = []
            batch_timeout = self._write_timeout
            if isinstance(obj, BatchWriteContext):
                if n != 0:
                    raise RuntimeError("Missing FlushPoint before Batch")
                if len(obj.requests) > self._MAX_WRITE_REQUEST_BATCH_SIZE:
                    for request in obj.requests:
                        request._mark_complete(False, "Batch too big")
                    break
                requests = obj.requests
                batch_timeout = obj.timeout
            elif isinstance(obj, WriteRequest):
                requests = [obj]
            else:
                raise RuntimeError("Unsupported element in write queue")

            for request in requests:
                if n < self._MAX_WRITE_REQUEST_BATCH_SIZE:
                    if request._watchable._server_id is not None:
                        api_req['updates'].append({
                            'batch_index': n,
                            'watchable': request._watchable._server_id,
                            'value': request._value
                        })
                        batch_dict[n] = request
                        n += 1
                    else:
                        request._mark_complete(False, "Watchable has been made invalid")
                else:
                    request._mark_complete(False, "Batch overflowed")   # Should never happen because we enforce n==0 on batch

            if n >= self._MAX_WRITE_REQUEST_BATCH_SIZE:
                break

        if len(api_req['updates']) == 0:
            return

        def _wt_write_watchable_response_callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK:
                confirmation = api_parser.parse_write_value_response(cast(api_typing.S2C.WriteValue, response))

                if confirmation.count != len(batch_dict):
                    request._mark_complete(False, f"Count mismatch in request and server confirmation.")
                else:
                    self._pending_api_batch_writes[confirmation.request_token] = PendingAPIBatchWrite(
                        update_dict=batch_dict,
                        confirmation=confirmation,
                        creation_timestamp=time.time(),
                        timeout=batch_timeout
                    )
            else:
                request._mark_complete(False, state.name)

        self._send(api_req, _wt_write_watchable_response_callback, timeout=batch_timeout)
        # We don't need the future object here because the WriteRequest act as one.

    def _wt_process_device_state(self) -> None:
        """Check the state of the device and take action when it changes"""
        if self._server_info is not None:
            # ====  Check Device conn
            if self._last_device_session_id is not None:
                if self._last_device_session_id != self._server_info.device_session_id:
                    self._wt_clear_all_watchables(ValueStatus.DeviceGone)
                    self._logger.info(f"Device is gone. Session ID: {self._last_device_session_id}")
            else:
                if self._server_info.device_session_id is not None:
                    device_name = "<unnamed>"
                    if self._server_info.device is not None:
                        device_name = self._server_info.device.display_name
                    self._logger.info(f"Connected to device. Name:{device_name} - Session ID: {self._server_info.device_session_id} ")

                    # ====  Check SFD
            new_firmware_id = self._server_info.sfd.firmware_id if self._server_info.sfd is not None else None
            if self._last_sfd_firmware_id is not None:
                if new_firmware_id is None:
                    self._wt_clear_all_watchables(ValueStatus.SFDUnloaded, [WatchableType.Alias, WatchableType.Variable])   # RPVs are still there.
                    self._logger.info(f"SFD unloaded. Firmware ID: {self._last_sfd_firmware_id}")
            else:
                if new_firmware_id is not None:
                    self._logger.info(f"SFD loaded. Firmware ID: {new_firmware_id}")

            self._last_device_session_id = self._server_info.device_session_id
            self._last_sfd_firmware_id = new_firmware_id
        else:
            self._last_device_session_id = None
            self._last_sfd_firmware_id = None

    def _wt_disconnect(self) -> None:
        """Disconnect from a Scrutiny server, called by the Worker Thread .
            Does not throw an exception in case of broken pipe
        """

        with self._conn_lock:
            if self._conn is not None:
                self._logger.info(f"Disconnecting from server at {self._hostname}:{self._port}")
                try:
                    self._conn.close_socket()
                except (websockets.exceptions.WebSocketException, socket.error):
                    self._logger.debug("Failed to close the websocket")
                    self._logger.debug(traceback.format_exc())

            self._conn = None

        with self._main_lock:
            self._hostname = None
            self._port = None
            self._server_state = ServerState.Disconnected
            self._server_info = None
            self._last_device_session_id = None

            self._wt_clear_all_watchables(ValueStatus.ServerGone)

            for callback_entry in self._callback_storage.values():
                if callback_entry._future.state == CallbackState.Pending:
                    callback_entry._future._wt_mark_completed(CallbackState.Cancelled)
            self._callback_storage.clear()

    def _wt_clear_all_watchables(self, new_status: ValueStatus, watchable_types: Optional[List[WatchableType]] = None) -> None:
        assert new_status is not ValueStatus.Valid
        if watchable_types is None:
            watchable_types = [WatchableType.Alias, WatchableType.Variable, WatchableType.RuntimePublishedValue]
        server_ids = list(self._watchable_storage.keys())
        for server_id in server_ids:
            watchable = self._watchable_storage[server_id]
            if watchable.type in watchable_types:
                watchable._set_invalid(new_status)
                if watchable.display_path in self._watchable_path_to_id_map:
                    del self._watchable_path_to_id_map[watchable.display_path]
                del self._watchable_storage[server_id]

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
        """Sends a message to the API. Return a future if a callback is specified. If no timeout is given, uses the default timeout value"""

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
                raise sdk.exceptions.ConnectionError(f"Disconnected from server")

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
            raise sdk.exceptions.ConnectionError(f"Disconnected from server. {error}")

        return future

    def _wt_recv(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        # No need to lock conn_lock here. Important is during disconnection
        error: Optional[Exception] = None
        obj: Optional[Dict[str, Any]] = None

        if self._conn is None:
            raise sdk.exceptions.ConnectionError(f"Disconnected from server")

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
            raise sdk.exceptions.ConnectionError(f"Disconnected from server. {error}")

        return obj

    def _make_request(self, command: str, data: Optional[Dict[str, Any]] = None) -> api_typing.C2SMessage:
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
        data = data.copy()
        data.update(cmd)

        return data

    def _enqueue_write_request(self, request: Union[WriteRequest, BatchWriteContext, FlushPoint]) -> None:
        self._write_request_queue.put(request)

    def __del__(self) -> None:
        self.disconnect()

    def _is_batch_write_in_progress(self) -> bool:
        return self._active_batch_context is not None

    def _process_write_request(self, request: WriteRequest) -> None:
        if self._is_batch_write_in_progress():
            assert self._active_batch_context is not None
            self._active_batch_context.requests.append(request)
        else:
            self._enqueue_write_request(request)

    def _flush_batch_write(self, batch_write_context: BatchWriteContext) -> None:
        self._enqueue_write_request(FlushPoint())   # Flush Point required because Python thread-safe queue has no peek() method.
        self._enqueue_write_request(batch_write_context)

    def _end_batch(self) -> None:
        self._active_batch_context = None

    def _wait_write_batch_complete(self, batch: BatchWriteContext) -> None:
        start_time = time.time()

        incomplete_count: Optional[int] = None
        try:
            for write_request in batch.requests:
                remaining_time = max(0, batch.timeout - (time.time() - start_time))
                write_request.wait_for_completion(timeout=remaining_time)
            timed_out = False
        except sdk.exceptions.TimeoutException:
            timed_out = True

        if timed_out:
            incomplete_count = 0
            for request in batch.requests:
                if not request.completed:
                    incomplete_count += 1

            if incomplete_count > 0:
                raise sdk.exceptions.TimeoutException(
                    f"Incomplete batch write. {incomplete_count} write requests not completed in {batch.timeout} sec. ")

    # === User API ====

    def connect(self, hostname: str, port: int, wait_status: bool = True, **kwargs: Dict[str, Any]) -> "ScrutinyClient":
        """Connect to a Scrutiny server through a websocket. Extra kwargs are passed down to `websockets.sync.client.connect()`

        :param hostname: The hostname or ip address of the server
        :param port: The listening port of the server
        :param wait_status: Wait for a server status update after the websocket connection is established. Ensure that a value is available when calling :meth:`get_server_status()<get_server_status>`

        :raise ConnectionError: In case of failure
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
                    self._conn = websockets.sync.client.connect(uri, **kwargs)  # type: ignore
                    self._server_state = ServerState.Connected
                    self._start_worker_thread()
                except (websockets.exceptions.WebSocketException, socket.error) as e:
                    self._logger.debug(traceback.format_exc())
                    connect_error = e

        if connect_error is not None:
            self.disconnect()
            raise sdk.exceptions.ConnectionError(f'Failed to connect to the server at "{uri}". Error: {connect_error}')
        else:
            if wait_status:
                self.wait_server_status_update()
        return self

    def disconnect(self) -> None:
        """Disconnect from the server"""
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

    def watch(self, path: str) -> WatchableHandle:
        """Starts watching a watchable element identified by its display path (tree-like path)

        :param path: The path of the element to watch

        :raise OperationFailure: If the watch request fails to complete
        :raise TypeError: Given parameter not of the expected type

        :return: A handle that can read/write the watched element.
        """
        validation.assert_type(path, 'path', str)

        cached_watchable: Optional[WatchableHandle] = None
        with self._main_lock:
            if path in self._watchable_path_to_id_map:
                server_id = self._watchable_path_to_id_map[path]
                if server_id in self._watchable_storage:
                    cached_watchable = self._watchable_storage[path]

        if cached_watchable is not None:
            return cached_watchable

        watchable = WatchableHandle(self, path)

        def wt_subscribe_callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK:
                response = cast(api_typing.S2C.SubscribeWatchable, response)
                watchable_defs = api_parser.parse_subscribe_watchable_response(response)
                if len(watchable_defs) != 1:
                    raise sdk.exceptions.BadResponseError(
                        f'The server did confirm the subscription of {len(response["subscribed"])} while we requested only for 1')

                if path not in watchable_defs:
                    raise sdk.exceptions.BadResponseError(
                        f'The server did not confirm the subscription for the right watchable. Got {list(response["subscribed"].keys())[0]}, expected {path}')

                watchable._configure(
                    datatype=watchable_defs[path].datatype,
                    watchable_type=watchable_defs[path].watchable_type,
                    server_id=watchable_defs[path].server_id,
                )

        req = self._make_request(API.Command.Client2Api.SUBSCRIBE_WATCHABLE, {
            'watchables': [watchable.display_path]  # Single element
        })
        future = self._send(req, wt_subscribe_callback)
        assert future is not None
        future.wait()

        if future.state != CallbackState.OK:
            raise sdk.exceptions.OperationFailure(f"Failed to subscribe to the watchable. {future.error_str}")

        assert watchable._server_id is not None
        with self._main_lock:
            self._watchable_path_to_id_map[watchable.display_path] = watchable._server_id
            self._watchable_storage[watchable._server_id] = watchable

        return watchable

    def unwatch(self, watchable_ref: Union[str, WatchableHandle]) -> None:
        """Stop watching a watchable element

        :param watchable_ref: The tree-like path of the watchable element or the handle to it

        :raise ValueError: If path is not valid
        :raise TypeError: Given parameter not of the expected type
        :raise NameNotFoundError: If the required path is not presently being watched
        :raise OperationFailure: If the subscription cancellation failed in any way
        """
        validation.assert_type(watchable_ref, 'watchable_ref', (str, WatchableHandle))
        if isinstance(watchable_ref, WatchableHandle):
            path = watchable_ref.display_path
        else:
            path = watchable_ref

        watchable: Optional[WatchableHandle] = None
        with self._main_lock:
            if path in self._watchable_path_to_id_map:
                server_id = self._watchable_path_to_id_map[path]
                if server_id in self._watchable_storage:
                    watchable = self._watchable_storage[server_id]

        if watchable is None:
            raise sdk.exceptions.NameNotFoundError(f"Cannot unwatch {path} as it is not being watched.")

        req = self._make_request(API.Command.Client2Api.UNSUBSCRIBE_WATCHABLE, {
            'watchables': [
                watchable.display_path
            ]
        })

        def wt_unsubscribe_callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK and watchable is not None:
                response = cast(api_typing.S2C.UnsubscribeWatchable, response)
                if len(response['unsubscribed']) != 1:
                    raise sdk.exceptions.BadResponseError(
                        f'The server did cancel the subscription of {len(response["unsubscribed"])} while we requested only for 1')

                if response['unsubscribed'][0] != watchable.display_path:
                    raise sdk.exceptions.BadResponseError(
                        f'The server did not cancel the subscription for the right watchable. Got {response["unsubscribed"][0]}, expected {watchable._server_id}')

        future = self._send(req, wt_unsubscribe_callback)
        assert future is not None
        error: Optional[Exception] = None
        try:
            future.wait()
        except sdk.exceptions.TimeoutException as e:
            error = e
        finally:
            with self._main_lock:
                if watchable.display_path in self._watchable_path_to_id_map:
                    del self._watchable_path_to_id_map[watchable.display_path]

                if watchable._server_id in self._watchable_storage:
                    del self._watchable_storage[watchable._server_id]

            watchable._set_invalid(ValueStatus.NotWatched)

        if error:
            raise error

        if future.state != CallbackState.OK:
            raise sdk.exceptions.OperationFailure(f"Failed to unsubscribe to the watchable. {future.error_str}")

    def wait_new_value_for_all(self, timeout: float = 5) -> None:
        """Wait for all watched elements to be updated at least once after the call to this method

        :param timeout: Amount of time to wait for the update

        :raise TypeError: Given parameter not of the expected type
        :raise ValueError: Given parameter has an invalid value
        :raise TimeoutException: If not all watched elements gets updated in time
        """
        timeout = validation.assert_float_range(timeout, 'timeout', minval=0)
        counter_map: Dict[str, Optional[int]] = {}
        with self._main_lock:
            watchable_storage_copy = self._watchable_storage.copy()  # Shallow copy

        for server_id in watchable_storage_copy:
            counter_map[server_id] = watchable_storage_copy[server_id]._update_counter

        start_time = time.time()
        for server_id in watchable_storage_copy:
            timeout_remainder = max(round(timeout - (time.time() - start_time), 2), 0)
            # Wait update will throw if the server has gone away as the _disconnect method will set all watchables "invalid"
            watchable_storage_copy[server_id].wait_update(previous_counter=counter_map[server_id], timeout=timeout_remainder)

    def wait_server_status_update(self, timeout: float = _UPDATE_SERVER_STATUS_INTERVAL + 0.5) -> None:
        """Wait for the server to broadcast a status update. Happens periodically

        :param timeout: Amount of time to wait for the update

        :raise TypeError: Given parameter not of the expected type
        :raise ValueError: Given parameter has an invalid value
        :raise TimeoutException: Server status update did not occurred within the timeout time
        """
        timeout = validation.assert_float_range(timeout, 'timeout', minval=0)
        self._threading_events.server_status_updated.clear()
        self._threading_events.server_status_updated.wait(timeout=timeout)

        if not self._threading_events.server_status_updated.is_set():
            raise sdk.exceptions.TimeoutException(f"Server status did not update within a {timeout} seconds delay")

    def wait_device_ready(self, timeout: float) -> None:
        """Wait for a device to be connected to the server and have finished its handshake.

        :param timeout: Amount of time to wait for the device

        :raise TypeError: Given parameter not of the expected type
        :raise ValueError: Given parameter has an invalid value
        :raise InvalidValueError: If the watchable becomes invalid while waiting
        :raise TimeoutException: If the device does not become ready within the required timeout
        """

        timeout = validation.assert_float_range(timeout, 'timeout', minval=0)

        t1 = time.monotonic()
        while True:
            server_status = self.get_server_status()
            if server_status is not None:
                if server_status.device_comm_state == sdk.DeviceCommState.ConnectedReady:
                    break
            consumed_time = time.monotonic()-t1
            remaining_time = max(timeout-consumed_time, 0)
            timed_out = False
            try:
                self.wait_server_status_update(remaining_time)
            except sdk.exceptions.TimeoutException:
                timed_out = True
            
            if timed_out:
                raise sdk.exceptions.TimeoutException(f'Device did not become ready within {timeout}s')

    def batch_write(self, timeout: Optional[float] = None) -> BatchWriteContext:
        """Starts a batch write. Write operations will be enqueued and committed together.
        Every write is guaranteed to be executed in the right order

        :param timeout: Amount of time to wait for the completion of the batch once committed. If ``None`` the default write timeout
            will be used.

        :raise TypeError: Given parameter not of the expected type
        :raise ValueError: Given parameter has an invalid value
        :raise OperationFailure: Failed to complete the batch write

        """
        timeout = validation.assert_float_range_if_not_none(timeout, 'timeout', minval=0)

        if self._active_batch_context is not None:
            raise sdk.exceptions.OperationFailure("Batch write cannot be nested")

        if timeout is None:
            timeout = self._write_timeout

        batch_context = BatchWriteContext(self, timeout)
        self._active_batch_context = batch_context
        return batch_context

    def get_installed_sfds(self) -> Dict[str, sdk.SFDInfo]:
        """Gets the list of Scrutiny Firmware Description file installed on the server

        :raise OperationFailure: Failed to get the SFD list

        :return: A dictionary mapping firmware IDS (hash) to a :class:`SFDInfo<scrutiny.sdk.SFDInfo>` structure
        """
        req = self._make_request(API.Command.Client2Api.GET_INSTALLED_SFD)

        @dataclass
        class Container:
            obj: Optional[Dict[str, sdk.SFDInfo]]

        cb_data: Container = Container(obj=None)  # Force pass by ref

        def callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK:
                cb_data.obj = api_parser.parse_get_installed_sfds_response(cast(api_typing.S2C.GetInstalledSFD, response))

        future = self._send(req, callback)
        assert future is not None
        future.wait()
        if future.state != CallbackState.OK or cb_data.obj is None:
            raise sdk.exceptions.OperationFailure(
                f"Failed to get the list of Scrutiny Firmware Description file installed on the server. {future.error_str}")

        return cb_data.obj

    def wait_process(self, timeout: Optional[float] = None) -> None:
        """Wait for the SDK thread to execute fully at least once. Useful for testing

        :param timeout: Amount of time to wait for the completion of the thread loops. If ``None`` the default timeout will be used.

        :raise TimeoutException: Worker thread does not complete a full loop within the given timeout
        """

        timeout = validation.assert_float_range_if_not_none(timeout, 'timeout', minval=0)

        if timeout is None:
            timeout = self._timeout
        self._threading_events.sync_complete.clear()
        self._threading_events.require_sync.set()
        self._threading_events.sync_complete.wait(timeout=timeout)
        if not self._threading_events.sync_complete.is_set():
            raise sdk.exceptions.TimeoutException(f"Worker thread did not complete a full loop within the {timeout} seconds.")

    def read_memory(self, address: int, size: int, timeout: Optional[float] = None) -> bytes:
        """Read the device memory synchronously.

        :param address: The start address of the region to read
        :param size: The size of the region to read, in bytes.
        :param timeout: Maximum amount of time to wait to get the data back. If ``None``, the default timeout value will be used

        :raise TypeError: Given parameter not of the expected type
        :raise ValueError: Given parameter has an invalid value
        :raise OperationFailure: Failed to complete the reading
        :raise TimeoutException: If the read operation does not complete within the given timeout value
        """

        validation.assert_int_range(address, 'address', minval=0)
        validation.assert_int_range(size, 'size', minval=1)
        timeout = validation.assert_float_range_if_not_none(timeout, 'timeout', minval=0)

        time_start = time.time()
        if timeout is None:
            timeout = self._timeout

        req = self._make_request(API.Command.Client2Api.READ_MEMORY, {
            'address': address,
            'size': size
        })

        @dataclass
        class Container:
            obj: Optional[str]
        cb_data: Container = Container(obj=None)  # Force pass by ref

        def callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK:
                response = cast(api_typing.S2C.ReadMemory, response)
                if 'request_token' not in response:
                    raise sdk.exceptions.BadResponseError('Missing request token in response')
                cb_data.obj = response['request_token']

        future = self._send(req, callback, timeout)
        assert future is not None
        future.wait()
        if future.state != CallbackState.OK or cb_data.obj is None:
            raise sdk.exceptions.OperationFailure(f"Failed to read the device memory. {future.error_str}")

        remaining_time = max(0, timeout - (time_start - time.time()))
        request_token = cb_data.obj

        t = time.time()
        # No lock here because we have a 1 producer, 1 consumer scenario and we are waiting. We don't write
        while request_token not in self._memory_read_completion_dict:
            if time.time() - t >= remaining_time:
                break
            time.sleep(0.002)

        with self._main_lock:
            if request_token not in self._memory_read_completion_dict:
                raise sdk.exceptions.TimeoutException(
                    "Did not get memory read result after %0.2f seconds. (address=0x%08X, size=%d)" % (timeout, address, size))

            completion = self._memory_read_completion_dict[request_token]
            del self._memory_read_completion_dict[request_token]

        if not completion.success or completion.data is None:
            raise sdk.exceptions.OperationFailure(f"Failed to read the device memory. {completion.error}")

        return completion.data

    def write_memory(self, address: int, data: bytes, timeout: Optional[float] = None) -> None:
        """Write the device memory synchronously. This method will exit once the write is completed otherwise will throw an exception in case of failure

        :param address: The start address of the region to read
        :param data: The data to write
        :param timeout: Maximum amount of time to wait to get the write completion confirmation. If ``None``, the default write timeout value will be used

        :raise TypeError: Given parameter not of the expected type
        :raise ValueError: Given parameter has an invalid value
        :raise OperationFailure: Failed to complete the reading
        :raise TimeoutException: If the read operation does not complete within the given timeout value

        """

        validation.assert_int_range(address, 'address', minval=0)
        validation.assert_type(data, 'data', bytes)
        timeout = validation.assert_float_range_if_not_none(timeout, 'timeout', minval=0)

        time_start = time.time()
        if timeout is None:
            timeout = self._timeout

        req = self._make_request(API.Command.Client2Api.WRITE_MEMORY, {
            'address': address,
            'data': b64encode(data).decode('ascii')
        })

        @dataclass
        class Container:
            obj: Optional[str]
        cb_data: Container = Container(obj=None)  # Force pass by ref

        def callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK:
                response = cast(api_typing.S2C.WriteMemory, response)
                if 'request_token' not in response:
                    raise sdk.exceptions.BadResponseError('Missing request token in response')
                cb_data.obj = response['request_token']

        future = self._send(req, callback, timeout)
        assert future is not None
        future.wait()
        if future.state != CallbackState.OK or cb_data.obj is None:
            raise sdk.exceptions.OperationFailure(f"Failed to write the device memory. {future.error_str}")

        remaining_time = max(0, timeout - (time_start - time.time()))
        request_token = cb_data.obj

        t = time.time()
        # No lock here because we have a 1 producer, 1 consumer scenario and are waiting. We don't write
        while request_token not in self._memory_write_completion_dict:
            if time.time() - t >= remaining_time:
                break
            time.sleep(0.002)

        with self._main_lock:
            if request_token not in self._memory_write_completion_dict:
                raise sdk.exceptions.OperationFailure(
                    "Did not get memory write completion confirmation after %0.2f seconds. (address=0x%08X, size=%d)" % (timeout, address, len(data)))

            completion = self._memory_write_completion_dict[request_token]
            del self._memory_write_completion_dict[request_token]

        if not completion.success:
            raise sdk.exceptions.OperationFailure(f"Failed to write the device memory. {completion.error}")

    def get_datalogging_capabilities(self) -> sdk.datalogging.DataloggingCapabilities:
        """Gets the device capabilities in terms of datalogging. This information includes the available sampling rates, the datalogging buffer size, 
        the data encoding format and the maximum number of signals. 

        :raise OperationFailure: If the request to the server fails

        :return: The datalogging capabilities
        """
        req = self._make_request(API.Command.Client2Api.GET_DATALOGGING_CAPABILITIES)

        @dataclass
        class Container:
            obj: Optional[sdk.datalogging.DataloggingCapabilities]
        cb_data: Container = Container(obj=None)  # Force pass by ref

        def callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK:
                cb_data.obj = api_parser.parse_get_datalogging_capabilities_response(cast(api_typing.S2C.GetDataloggingCapabilities, response))
        future = self._send(req, callback)
        assert future is not None
        future.wait()

        if future.state != CallbackState.OK:
            raise sdk.exceptions.OperationFailure(f"Failed to read the datalogging capabilities. {future.error_str}")

        if cb_data.obj is None:
            raise sdk.exceptions.OperationFailure(f"Datalogging capabilities are not available at this moment.")

        return cb_data.obj

    def read_datalogging_acquisition(self, reference_id: str, timeout: Optional[float] = None) -> sdk.datalogging.DataloggingAcquisition:
        """Reads a datalogging acquisition from the server storage identified by its reference ID

        :param reference_id: The acquisition unique ID
        :param timeout: The request timeout value. The default client timeout will be used if set to ``None`` Defaults to ``None``

        :raise OperationFailure: If fetching the acquisition fails

        :return: An object containing the acquisition, including the data, the axes, the trigger index, the graph name, etc
        """
        validation.assert_type(reference_id, 'reference_id', str)
        timeout = validation.assert_float_range_if_not_none(timeout, 'timeout', minval=0)

        if timeout is None:
            timeout = self._timeout

        req = self._make_request(API.Command.Client2Api.READ_DATALOGGING_ACQUISITION_CONTENT, {
            'reference_id': reference_id
        })

        @dataclass
        class Container:
            obj: Optional[sdk.datalogging.DataloggingAcquisition]
        cb_data: Container = Container(obj=None)  # Force pass by ref

        def callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK:
                cb_data.obj = api_parser.parse_read_datalogging_acquisition_content_response(
                    cast(api_typing.S2C.ReadDataloggingAcquisitionContent, response)
                )
        future = self._send(req, callback)
        assert future is not None
        future.wait(timeout)

        if future.state != CallbackState.OK:
            raise sdk.exceptions.OperationFailure(
                f"Failed to read the datalogging acquisition with reference ID '{reference_id}'. {future.error_str}")

        assert cb_data.obj is not None
        acquisition = cb_data.obj
        return acquisition

    def start_datalog(self, config: sdk.datalogging.DataloggingConfig) -> sdk.datalogging.DataloggingRequest:
        """Requires the device to make a datalogging acquisition based on the given configuration

        :param config: The datalogging configuration including sampling rate, signals to log, trigger condition and operands, etc.

        :raise OperationFailure: If the request to the server fails
        :raise ValueError: Bad parameter value
        :raise TypeError: Given parameter not of the expected type

        :return: A `DataloggingRequest` handle that can provide the status of the acquisition process and used to fetch the data.
         """
        validation.assert_type(config, 'config', sdk.datalogging.DataloggingConfig)

        req_data: api_typing.C2S.RequestDataloggingAcquisition = {
            'cmd': "",  # Will be overridden
            "reqid": 0,  # Will be overridden

            'condition': config._trigger_condition.value,
            'sampling_rate_id': config._sampling_rate,
            'decimation': config._decimation,
            'name': config._name,
            'timeout': config._timeout,
            'trigger_hold_time': config._trigger_hold_time,
            'probe_location': config._trigger_position,
            'x_axis_type': config._x_axis_type.value,
            'x_axis_signal': config._get_api_x_axis_signal(),
            'yaxes': config._get_api_yaxes(),
            'operands': config._get_api_trigger_operands(),
            'signals': config._get_api_signals(),
        }

        req = self._make_request(API.Command.Client2Api.REQUEST_DATALOGGING_ACQUISITION, cast(Dict[str, Any], req_data))

        @dataclass
        class Container:
            request: Optional[sdk.datalogging.DataloggingRequest]
        cb_data: Container = Container(request=None)  # Force pass by ref

        def callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK:
                request_token = api_parser.parse_request_datalogging_acquisition_response(
                    cast(api_typing.S2C.RequestDataloggingAcquisition, response)
                )
                cb_data.request = sdk.datalogging.DataloggingRequest(client=self, request_token=request_token)
                self._pending_datalogging_requests[request_token] = cb_data.request

        future = self._send(req, callback)
        assert future is not None
        future.wait()

        if future.state != CallbackState.OK:
            raise sdk.exceptions.OperationFailure(
                f"Failed to request the datalogging acquisition'. {future.error_str}")
        assert cb_data.request is not None
        return cb_data.request

    def list_stored_datalogging_acquisitions(self, timeout: Optional[float] = None) -> List[sdk.datalogging.DataloggingStorageEntry]:
        """Gets the list of datalogging acquisition stored in the server database

        :param timeout: The request timeout value. The default client timeout will be used if set to ``None`` Defaults to ``None``

        :raise OperationFailure: If fetching the list fails

        :return: A list of database entries, each one representing an acquisition in the database with `reference_id` as its unique identifier
        """
        timeout = validation.assert_float_range_if_not_none(timeout, 'timeout', minval=0)

        if timeout is None:
            timeout = self._timeout

        req = self._make_request(API.Command.Client2Api.LIST_DATALOGGING_ACQUISITION)

        @dataclass
        class Container:
            obj: Optional[List[sdk.datalogging.DataloggingStorageEntry]]
        cb_data: Container = Container(obj=None)  # Force pass by ref

        def callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK:
                cb_data.obj = api_parser.parse_list_datalogging_acquisitions_response(
                    cast(api_typing.S2C.ListDataloggingAcquisition, response)
                )
        future = self._send(req, callback)
        assert future is not None
        future.wait(timeout)

        if future.state != CallbackState.OK:
            raise sdk.exceptions.OperationFailure(
                f"Failed to read the datalogging acquisition list from the server database. {future.error_str}")

        assert cb_data.obj is not None
        return cb_data.obj

    def configure_device_link(self, link_type: sdk.DeviceLinkType, link_config: Optional[sdk.BaseLinkConfig]) -> None:
        """Configure the communication link between the Scrutiny server and the device remote device. 
        If the link is configured in a way that a Scrutiny device is accessible, the server will automatically
        connect to it and inform the client about it. The `client.server.server_state.device_comm_state` will reflect this.

        :param link_type: Type of communication link to use. Serial, UDP, TCP, etc.
        :param link_config:  A configuration object that matches the link type.
            :attr:`UDP<scrutiny.sdk.DeviceLinkType.UDP>` : :class:`UDPLinkConfig<scrutiny.sdk.UDPLinkConfig>` /
            :attr:`TCP<scrutiny.sdk.DeviceLinkType.TCP>` : :class:`TCPLinkConfig<scrutiny.sdk.TCPLinkConfig>` /
            :attr:`Serial<scrutiny.sdk.DeviceLinkType.Serial>` : :class:`SerialLinkConfig<scrutiny.sdk.SerialLinkConfig>`

        :raise ValueError: Bad parameter value
        :raise TypeError: Given parameter not of the expected type
        :raise OperationFailure: If the request to the server fails
        """

        validation.assert_type(link_type, "link_type", sdk.DeviceLinkType)
        validation.assert_type(link_config, "link_config", sdk.BaseLinkConfig)

        assert link_type is not None
        assert link_config is not None

        api_map: Dict["DeviceLinkType", Tuple[str, Type[Union[BaseLinkConfig, None]]]] = {
            DeviceLinkType.Serial: ('serial', sdk.SerialLinkConfig),
            DeviceLinkType.UDP: ('udp', sdk.UDPLinkConfig),
            DeviceLinkType.TCP: ('tcp', sdk.TCPLinkConfig),
            DeviceLinkType._DummyThreadSafe: ('thread_safe_dummy', type(None)),
            DeviceLinkType._Dummy: ('dummy', type(None))
        }

        if link_type not in api_map:
            raise ValueError(f"Unsupported link type : {link_type.name}")

        link_type_api_name, config_type = api_map[link_type]

        if not isinstance(link_config, config_type):
            raise TypeError(f'link_config must be of type {config_type} when link_type is {link_type.name}. Got {link_type.__class__.__name__}')

        req = self._make_request(API.Command.Client2Api.SET_LINK_CONFIG, {
            'link_type': link_type_api_name,
            'link_config': link_config._to_api_format()
        })

        future = self._send(req, lambda *args, **kwargs: None)
        assert future is not None
        future.wait()

        if future.state != CallbackState.OK:
            raise sdk.exceptions.OperationFailure(
                f"Failed to configure the device communication link'. {future.error_str}")

    def user_command(self, subfunction: int, data: bytes = bytes()) -> sdk.UserCommandResponse:
        """
        Sends a UserCommand request to the device with the given subfunction and data. UserCommand is a request that calls a user defined callback
        in the device firmware. It allows a developer to take advantage of the scrutiny protocol to communicate non-scrutiny data with its device.

        :param subfunction: Subfunction of the request. From 0x0 to 0x7F
        :param data: The payload to send to the device

        :raise ValueError: Bad parameter value
        :raise TypeError: Given parameter not of the expected type
        :raise OperationFailure: If the command completion fails
        """
        validation.assert_int_range(subfunction, 'subfunction', 0, 0xFF)
        validation.assert_type(data, 'data', bytes)

        req = self._make_request(API.Command.Client2Api.USER_COMMAND, {
            'subfunction': subfunction,
            'data': b64encode(data).decode('utf8')
        })

        @dataclass
        class Container:
            obj: Optional[sdk.UserCommandResponse]
        cb_data: Container = Container(obj=None)  # Force pass by ref

        def wt_user_command_callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK:
                response = cast(api_typing.S2C.UserCommand, response)
                cb_data.obj = api_parser.parse_user_command_response(response)

        future = self._send(req, wt_user_command_callback)
        assert future is not None
        future.wait()

        if future.state != CallbackState.OK or cb_data.obj is None:
            raise sdk.exceptions.OperationFailure(f"Failed to request the device UserCommand. {future.error_str}")

        return cb_data.obj

    def get_server_status(self) -> ServerInfo:
        """Returns an immutable structure of data containing the latest server status that has been broadcasted.
          It contains everything going on the server side

        :raise ConnectionError: If the connection to the server is lost
        :raise InvalidValueError: If the server status is not available (never received it).
        """

        # server_info is readonly and only its reference gets changed when updated.
        # We can safely return a reference here. The user can't mess it up
        with self._main_lock:
            if not self._server_state == ServerState.Connected:
                raise sdk.exceptions.ConnectionError(f"Disconnected from server")
            info = self._server_info
        if info is None:
            raise sdk.exceptions.InvalidValueError("Server status is not available")
        return info

    @property
    def name(self) -> str:
        return '' if self._name is None else self.name

    @property
    def server_state(self) -> ServerState:
        """The server communication state"""
        with self._main_lock:
            val = self._server_state  # Can be modified by the worker_thread
        return val

    @property
    def hostname(self) -> Optional[str]:
        """Hostname of the server used for websocket connection"""
        with self._main_lock:
            val = self._hostname  # Can be modified by the worker_thread
        return val

    @property
    def port(self) -> Optional[int]:
        """Port of the websocket"""
        with self._main_lock:
            val = self._port  # Can be modified by the worker_thread
        return val
