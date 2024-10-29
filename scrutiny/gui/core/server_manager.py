#    server_manager.py
#        Object that handles the communication with the server and inform the rest of the
#         GUI about what's happening on the other side of the socket. Based on the SDK ScrutinyClient
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['ServerManager', 'ServerConfig']

from scrutiny import sdk
from scrutiny.sdk.client import ScrutinyClient, WatchableListDownloadRequest
import threading
import time
import traceback
from dataclasses import dataclass

from PySide6.QtCore import Signal, QObject
from typing import Optional, Dict, Any, Callable
import logging

from scrutiny.gui.core.watchable_index import WatchableIndex

@dataclass
class ServerConfig:
    hostname:str
    port:int

class ClientRequestStore:
    @dataclass
    class ClientRequestEntry:
        ui_callback: Callable[[Any, Optional[Exception]], None]
        threaded_func_return_value:Any
        error:Optional[Exception]

    _next_id:int
    _storage:Dict[int, ClientRequestEntry]
    _lock:threading.Lock
    def __init__(self) -> None:
        self._next_id = 0
        self._storage = dict()
        self._lock = threading.Lock()
    
    def clear(self) -> None:
        with self._lock:
            self._storage.clear()
            self._next_id = 0
    
    def register(self, entry:ClientRequestEntry) -> int:
        with self._lock:
            while self._next_id in self._storage:
                self._next_id += 1
            assigned_id = self._next_id
            self._storage[assigned_id] = entry
            self._next_id+=1
        
        return assigned_id
        
    def get(self, storage_id:int) -> Optional[ClientRequestEntry]:
        try:
            with self._lock:
                entry = self._storage[storage_id]
                del self._storage[storage_id]
            return entry
        except KeyError:
            return None
        
        
        
class ServerManager:
    """Runs a thread for the synchronous SDK and emit QT events when something interesting happens"""

    class ThreadFSMData:
        """Data used by the server thread used to detect changes and emit events"""
        previous_server_state:sdk.ServerState
        server_state:sdk.ServerState
        server_info:Optional[sdk.ServerInfo]
        previous_server_info:Optional[sdk.ServerInfo]
        
        runtime_watchables_download_request:Optional[WatchableListDownloadRequest]
        sfd_watchables_download_request:Optional[WatchableListDownloadRequest]

        connect_timestamp_mono:Optional[float]

        def __init__(self) -> None:
            self.clear()

        def clear(self) -> None:
            self.sfd_watchables_download_request = None
            self.runtime_watchables_download_request = None
            self.previous_server_state = sdk.ServerState.Disconnected
            self.server_state = sdk.ServerState.Disconnected
            self.server_info = None
            self.previous_server_info = None
            self.connect_timestamp_mono = None
            self.clear_download_requests()
        
        def clear_download_requests(self) -> None:
            # RPV request
            req = self.runtime_watchables_download_request  # Get a reference atomically
            if req is not None:
                req.cancel()
            self.runtime_watchables_download_request = None

            # Alias/Var request
            req = self.sfd_watchables_download_request
            if req is not None:
                req.cancel()
            self.sfd_watchables_download_request = None


    class _InternalSignals(QObject):
        thread_exit_signal = Signal()
        client_request_completed = Signal(int)


    class _Signals(QObject):    # QObject required for signals to work
        """Signals offered to the outside world"""
        started = Signal()
        starting = Signal()
        stopping = Signal()
        stopped = Signal()
        server_connected = Signal()
        server_disconnected = Signal()
        device_ready = Signal()
        device_disconnected = Signal()
        datalogging_state_changed = Signal()
        sfd_loaded = Signal()
        sfd_unloaded = Signal()
        index_changed = Signal()
        status_received = Signal()

    RECONNECT_DELAY = 1
    _client:ScrutinyClient              # The SDK client object that talks with the server
    _thread:Optional[threading.Thread]  # The thread tyhat runs the synchronous client
    _index:WatchableIndex

    _thread_stop_event:threading.Event  # Event used to stop the thread
    _signals:_Signals                   # The signals
    _internal_signals:_InternalSignals
    _auto_reconnect:bool                # Flag indicating if the thread should try to reconnect the client if disconnected
    _logger:logging.Logger              # Logger
    _fsm_data:ThreadFSMData             # Data used by the thread to detect state changes

    _stop_pending:bool
    _client_request_store:ClientRequestStore

    def __init__(self, watchable_index:WatchableIndex, client:Optional[ScrutinyClient]=None) -> None:
        super().__init__()  # Required for signals to work
        self._logger = logging.getLogger(self.__class__.__name__)

        if client is None:
            self._client = ScrutinyClient()
        else:
            self._client = client   # Mainly useful for unit testing
        self._signals = self._Signals()
        self._internal_signals = self._InternalSignals()
        
        self._thread = None
        self._thread_stop_event = threading.Event()
        self._auto_reconnect = False
        
        self._fsm_data = self.ThreadFSMData()
        self._index = watchable_index

        self._internal_signals.thread_exit_signal.connect(self._join_thread_and_emit_stopped)
        self._internal_signals.client_request_completed.connect(self._client_request_completed)
        self._stop_pending = False
        self._client_request_store = ClientRequestStore()

    def _join_thread_and_emit_stopped(self) -> None:
        if self._thread is not None:    # Should always be true
            self._thread.join(0.5)    # Should be already dead if that signal came in. Wil join instantly
            if self._thread.is_alive():
                self._logger.error("Failed to stop the internal thread")
            else:
                self._logger.debug("Server manager stopped")
        self._thread = None
        self._stop_pending = False
        self.signals.stopped.emit()

    @property
    def signals(self) -> _Signals:
        """The events exposed to the application"""
        return self._signals

    @property
    def index(self) -> WatchableIndex:
        """The watchable index containing a definition of all the watchables available on the server"""
        return self._index

    
    def start(self, config:ServerConfig) -> None:
        """Makes the server manager try to connect and monitor server state changes
        Will autoreconnect on disconnection
        """
        self._logger.debug("ServerManager.start() called")
        if self.is_running():
            raise RuntimeError("Already running")   # Temporary hard check for debug
        
        if self._stop_pending:
            raise RuntimeError("Stop pending") # Temporary hard check for debug
        
        self._logger.debug("Starting server manager")
        self._client_request_store.clear()
        self.signals.starting.emit()
        self._auto_reconnect = True
        self._thread_stop_event.clear()
        self._thread = threading.Thread(target=self._thread_func, args=[config], daemon=True)
        self._thread.start()
        self._logger.debug("Server manager started")
        self.signals.started.emit()
    
    def stop(self) -> None:
        """Stops the server manager. Will disconnect it from the server and clear all internal data"""
        self._logger.debug("ServerManager.stop() called")
        if self._stop_pending:
            self._logger.debug("Stop already pending. Cannot stop")
            return
        
        if not self.is_running():
            self._logger.debug("Server manager is not running. Cannot stop")
            return 
        
        self._stop_pending = True
        self._logger.debug("Stopping server manager")
        self.signals.stopping.emit()
        self._auto_reconnect = False
        self._client.close_socket()   # Will cancel any pending request in the other thread
        
        # Will cause the thread to exit and emit thread_exit_signal that triggers _join_thread_and_emit_stopped in the UI thread
        self._thread_stop_event.set()
        self._logger.debug("Stop initiated")

    def _thread_func(self, config:ServerConfig) -> None:
        """Thread that monitors state change on the server side"""
        self._logger.debug("Server manager thread running")
        self._fsm_data.previous_server_state = sdk.ServerState.Disconnected
        self._fsm_data.server_state = sdk.ServerState.Disconnected
        self._fsm_data.server_info = None
        self._fsm_data.previous_server_info = None
        self._fsm_data.connect_timestamp_mono = None
        try:
            while not self._thread_stop_event.is_set():
                self._fsm_data.server_state = self._client.server_state
                state_entry = self._fsm_data.server_state != self._fsm_data.previous_server_state
                if state_entry:
                    self._logger.debug(f"Switching state from {self._fsm_data.previous_server_state.name} to {self._fsm_data.server_state.name}")
                
                if self._fsm_data.server_state == sdk.ServerState.Disconnected:
                    if state_entry: # Will not enter on first loop. On purpose.
                        self._logger.debug("Entering disconnected state")
                        self._signals.server_disconnected.emit()
                        self._fsm_data.clear_download_requests()
                        self._clear_index()
                        self._fsm_data.server_info = None
                        self._fsm_data.previous_server_info = None

                    if self._auto_reconnect:
                        # timer to prevent going crazy on function call
                        if self._fsm_data.connect_timestamp_mono is None or time.monotonic() - self._fsm_data.connect_timestamp_mono > self.RECONNECT_DELAY:
                            try:
                                self._logger.debug("Connecting client")
                                self._fsm_data.connect_timestamp_mono = time.monotonic()
                                self._client.connect(config.hostname, config.port, wait_status=False)
                            except sdk.exceptions.ConnectionError:
                                pass
                
                elif self._fsm_data.server_state == sdk.ServerState.Connecting: # pragma: no cover
                    pass    # This state should never happen here because connect block until completion or failure

                elif self._fsm_data.server_state == sdk.ServerState.Connected:
                    if state_entry:
                        self._logger.debug(f"Client connected to {config.hostname}:{config.port}")
                        self._signals.server_connected.emit()
                        self._fsm_data.server_info = None
                        self._fsm_data.previous_server_info = None

                    try:
                        self._client.wait_server_status_update(0.2)
                        self._fsm_data.server_info = self._client.get_latest_server_status()
                        self.signals.status_received.emit()
                    except sdk.exceptions.TimeoutException:
                        pass
                    except sdk.exceptions.ScrutinySDKException:
                        self._fsm_data.server_info = None

                    # Server is gone
                    if self._fsm_data.server_info is None and self._fsm_data.previous_server_info is not None:
                        self._clear_index()
                        if self._fsm_data.previous_server_info.sfd is not None:
                            self._thread_sfd_unloaded()          # No event to avoid sending twice
                        if self._fsm_data.previous_server_info.device_session_id is not None:
                            self._thread_device_disconnected()   # No event to avoid sending twice
                    
                    # Server just arrived
                    elif self._fsm_data.server_info is not None and self._fsm_data.previous_server_info is None:
                        if self._fsm_data.server_info.device_session_id is not None:
                            self._thread_device_ready()
                            if self._fsm_data.server_info.sfd is not None:
                                self._thread_sfd_loaded()


                    # Server is running
                    elif self._fsm_data.server_info is not None and self._fsm_data.previous_server_info is not None:
                        # Device just left
                        if self._fsm_data.server_info.device_session_id is None and self._fsm_data.previous_server_info.device_session_id is not None:
                            self._clear_index()
                            if self._fsm_data.server_info.sfd is None and self._fsm_data.previous_server_info.sfd is not None:
                                self._thread_sfd_unloaded()
                            self._thread_device_disconnected()

                        # Device just arrived
                        elif self._fsm_data.server_info.device_session_id is not None and self._fsm_data.previous_server_info.device_session_id is None:
                            self._thread_device_ready()
                            if self._fsm_data.server_info.sfd is not None and self._fsm_data.previous_server_info.sfd is None:
                                self._thread_sfd_loaded()

                        # Device has been there consistently
                        elif self._fsm_data.server_info.device_session_id is not None and self._fsm_data.previous_server_info.device_session_id is not None:
                            if self._fsm_data.server_info.device_session_id != self._fsm_data.previous_server_info.device_session_id:
                                # The server did a full reconnect between 2 state update.
                                # This state hsa a value only when device state is ConnectedReady
                                
                                self._clear_index()

                                if self._fsm_data.previous_server_info.sfd is not None:
                                    self._thread_sfd_unloaded()
                                self._thread_device_disconnected()
                                self._thread_device_ready()
                                if self._fsm_data.server_info.sfd is not None:
                                    self._thread_sfd_loaded()
                            else:
                                if self._fsm_data.server_info.sfd is None and self._fsm_data.previous_server_info.sfd is not None:
                                    self._thread_sfd_unloaded()
                                elif self._fsm_data.server_info.sfd is not None and self._fsm_data.previous_server_info.sfd is None:
                                    self._thread_sfd_loaded()
                                else:
                                    pass # SFD state is unchanged (None/None or loaded/loaded). Nothing to do

                            # Check change on datalogging state
                            if (self._fsm_data.server_info.datalogging.state != self._fsm_data.previous_server_info.datalogging.state 
                                or self._fsm_data.server_info.datalogging.completion_ratio != self._fsm_data.previous_server_info.datalogging.completion_ratio):
                                self._signals.datalogging_state_changed.emit()

                        else: # Both None, nothing to do
                            pass

                        self._thread_handle_download_watchable_logic()
                    else:
                        pass # Nothing to do

                    self._fsm_data.previous_server_info=self._fsm_data.server_info

                elif self._fsm_data.server_state == sdk.ServerState.Error:
                    self._logger.error("Server state is Error. Stopping the server manager")
                    if self._fsm_data.previous_server_state == sdk.ServerState.Connected:
                        self._signals.server_disconnected.emit()
                    self._auto_reconnect = False
                    self._thread_stop_event.set()

                self._fsm_data.previous_server_state = self._fsm_data.server_state

            
        except Exception as e:  # pragma: no cover
            self._logger.critical(f"Error in server manager thread: {e}")
            self._logger.debug(traceback.format_exc())
        finally:
            self._client.disconnect()
            if self._fsm_data.previous_server_state == sdk.ServerState.Connected:
                try:
                    self._signals.server_disconnected.emit()
                except RuntimeError:
                    pass    # May fail if the window is deleted before this thread exits
        
        self._fsm_data.clear()
        
        # Ensure the server thread has the time to notice the changes and emit all signals
        t = time.perf_counter()
        timeout = 1
        while self._client.server_state != sdk.ServerState.Disconnected and time.perf_counter() - t < timeout:
            time.sleep(0.01)
        
        self._logger.debug("Server Manager thread exiting")
        try:
            self._internal_signals.thread_exit_signal.emit()
        except RuntimeError:
            pass    # May fail if the window is deleted before this thread exits


    def _thread_handle_download_watchable_logic(self) -> None:
        # Handle download of RPV if the device is ready
        device_ready = False
        if self._fsm_data.server_info is not None:
            device_ready = self._fsm_data.server_info.device_session_id is not None
        
        if device_ready:
            if self._fsm_data.runtime_watchables_download_request is not None:
                if self._fsm_data.runtime_watchables_download_request.completed:  
                    # Download is finished
                    # Data is already inside the index. Added from the callback
                    was_success = self._fsm_data.runtime_watchables_download_request.is_success
                    self._fsm_data.runtime_watchables_download_request = None   # Clear the request.
                    self._logger.debug("Download of watchable list is complete. Group : runtime")
                    if was_success:
                        self._signals.index_changed.emit()
                    else:
                        self._clear_index_rpv()
                else:
                    pass # Downloading
        else:
            if self._index.has_data(sdk.WatchableType.RuntimePublishedValue): # pragma: no cover
                self._logger.critical("The device is not available but there is still data in the watchable index.")
                self._clear_index()

    
        # Handle the download of variables and alias if the SFD is loaded
        sfd_loaded = False
        if self._fsm_data.server_info is not None:
            sfd_loaded = self._fsm_data.server_info.sfd is not None
        if sfd_loaded:
                if self._fsm_data.sfd_watchables_download_request is not None: 
                    if self._fsm_data.sfd_watchables_download_request.completed:
                        # Download complete
                        # Data is already inside the index. Added from the callback
                        self._logger.debug("Download of watchable list is complete. Group : SFD")
                        was_success = self._fsm_data.sfd_watchables_download_request.is_success
                        self._fsm_data.sfd_watchables_download_request = None    # Clear the request.
                        if was_success:
                            self._signals.index_changed.emit()
                        else:
                            self._clear_index_alias_var()
                    else:
                        pass    # Downloading

        else:   # No SFD loaded
            if self._index.has_data(sdk.WatchableType.Alias) or self._index.has_data(sdk.WatchableType.Variable):   # pragma: no cover
                self._logger.critical("The SFD is not loaded but there is still data in the watchable index.")
                self._clear_index()

 
    def _thread_device_ready(self) -> None:
        """To be called once when a device connects"""
        self._logger.debug("Detected device ready")
        self._fsm_data.clear_download_requests()
        had_data = self._clear_index(no_changed_event=True) # Event is triggered AFTER device_ready
        self._fsm_data.runtime_watchables_download_request = self._client.download_watchable_list(
            types=[sdk.WatchableType.RuntimePublishedValue],
            partial_reception_callback=self._download_data_partial_response_callback
            )
        self._signals.device_ready.emit()
        if had_data:
            self.signals.index_changed.emit()

    def _thread_sfd_loaded(self) -> None:
        """To be called once when a SFD is laoded"""
        self._logger.debug("Detected SFD loaded")
        req = self._fsm_data.sfd_watchables_download_request    # Get the ref atomically
        if req is not None:
            req.cancel()
        had_data = self._clear_index_alias_var(no_changed_event=True) # Event is triggered AFTER sfd_loaded
        self._fsm_data.sfd_watchables_download_request = self._client.download_watchable_list(
            types=[sdk.WatchableType.Variable,sdk.WatchableType.Alias],
            partial_reception_callback=self._download_data_partial_response_callback
            )
        self.signals.sfd_loaded.emit()
        if had_data:
            self.signals.index_changed.emit()

    
    def _thread_sfd_unloaded(self, no_index_event:bool=False) -> None:
        """To be called once when a SFD is unloaded"""
        self._logger.debug("Detected SFD unloaded")
        req = self._fsm_data.sfd_watchables_download_request    # Get the ref atomically
        if req is not None:
            req.cancel()
        self._fsm_data.sfd_watchables_download_request = None
        self._clear_index_alias_var()
        self.signals.sfd_unloaded.emit()


    def _thread_device_disconnected(self) -> None:
        """To be called once when a device disconnect"""
        self._logger.debug("Detected device disconnected")
        self._fsm_data.clear_download_requests()
        self._clear_index()
        self._signals.device_disconnected.emit()
    
    def _download_data_partial_response_callback(self, 
        data:Dict[sdk.WatchableType, Dict[str, sdk.WatchableConfiguration]], 
        last_segment:bool) -> None:
        # This method is called from within the client internal worker thread
        # Qt signals are thread safe.

        if self._logger.isEnabledFor(logging.DEBUG):    # pragma: no cover
            stats = dict(zip([x.name for x in data.keys()], [len(x) for x in data.values()]))
            self._logger.debug(f"Received data. Count {stats}")

        self._index.add_content(data)   # Thread safe method
        if last_segment:
            self._logger.debug("Finished downloading watchable list")

    def _clear_index(self, no_changed_event:bool=False) -> bool:
        had_data = self._index.clear()
        if had_data and not no_changed_event:
            self.signals.index_changed.emit()
        return had_data
    
    def _clear_index_alias_var(self, no_changed_event:bool=False) -> bool:
        had_data_alias = self._index.clear_content_by_type(sdk.WatchableType.Alias)
        had_data_var = self._index.clear_content_by_type(sdk.WatchableType.Variable)
        had_data = had_data_var or had_data_alias
        if had_data and not no_changed_event:
            self.signals.index_changed.emit()
        return had_data
    
    def _clear_index_rpv(self, no_changed_event:bool=False) -> bool:
        had_data = self._index.clear_content_by_type(sdk.WatchableType.RuntimePublishedValue)
        if had_data and not no_changed_event:
            self.signals.index_changed.emit()
        return had_data

    def get_server_state(self) -> sdk.ServerState:
        return self._client.server_state
    
    def get_server_info(self) -> Optional[sdk.ServerInfo]:
        try:
            return self._client.get_latest_server_status()
        except sdk.exceptions.ScrutinySDKException:
            return None
    
    def is_running(self) -> bool:
        """Returns ``True`` if the server manager is started and fully working."""
        return self._thread is not None and self._thread.is_alive() and not self._stop_pending

    def is_stopping(self) -> bool:
        """Returns ``True`` if ``stop()`` has been called but the internal thread has not yet exited."""
        return self._stop_pending

    def _client_request_completed(self, store_id:int) -> None:
        # This runs in the UI thread
        entry = self._client_request_store.get(store_id)
        if entry is not None:
            entry.ui_callback(entry.threaded_func_return_value, entry.error)
        

    def schedule_client_request(self, 
            user_func:Callable[[ScrutinyClient], Any], 
            ui_thread_callback:Callable[[Any, Optional[Exception]], None]
            ) -> None:
        """Runs a client request in a separate thread and call a callback in the UI thread when done."""

        def threaded_func() -> None:
            # This runs in a separate thread
            error: Optional[Exception] = None
            return_val:Any = None
            try:
                return_val = user_func(self._client)
            except Exception as e:
                error = e

            entry = ClientRequestStore.ClientRequestEntry(
                ui_callback=ui_thread_callback,
                threaded_func_return_value=return_val,
                error=error
            )
            assigned_id = self._client_request_store.register(entry)
            self._internal_signals.client_request_completed.emit(assigned_id)

        t = threading.Thread(target=threaded_func, daemon=True)
        t.start()