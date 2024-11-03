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

    class ThreadState:
        """Data used by the server thread used to detect changes and emit events"""
        runtime_watchables_download_request:Optional[WatchableListDownloadRequest]
        sfd_watchables_download_request:Optional[WatchableListDownloadRequest]
        connect_timestamp_mono:Optional[float]
        last_server_state:sdk.ServerState

        def __init__(self) -> None:
            self.runtime_watchables_download_request = None
            self.sfd_watchables_download_request = None
            self.connect_timestamp_mono = None
            
            self.clear()

        def clear(self) -> None:
            self.connect_timestamp_mono = None
            self.last_server_state = sdk.ServerState.Disconnected
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
    _allow_auto_reconnect:bool                # Flag indicating if the thread should try to reconnect the client if disconnected
    _logger:logging.Logger              # Logger
    _thread_state:ThreadState             # Data used by the thread to detect state changes

    _stop_pending:bool
    _client_request_store:ClientRequestStore

    def __init__(self, watchable_index:WatchableIndex, client:Optional[ScrutinyClient]=None) -> None:
        super().__init__()  # Required for signals to work
        self._logger = logging.getLogger(self.__class__.__name__)

        if client is None:
            self._client = ScrutinyClient()
        else:
            self._client = client   # Mainly useful for unit testing
        self._client.listen_events(ScrutinyClient.Events.LISTEN_ALL)
        self._signals = self._Signals()
        self._internal_signals = self._InternalSignals()
        
        self._thread = None
        self._thread_stop_event = threading.Event()
        self._allow_auto_reconnect = False
        
        self._thread_state = self.ThreadState()
        self._index = watchable_index

        self._internal_signals.thread_exit_signal.connect(self._join_thread_and_emit_stopped)
        self._internal_signals.client_request_completed.connect(self._client_request_completed)
        self._stop_pending = False
        self._client_request_store = ClientRequestStore()

        if self._logger.isEnabledFor(logging.DEBUG):
            self._signals.server_connected.connect(lambda : self._logger.debug("+Signal: server_connected"))
            self._signals.server_disconnected.connect(lambda : self._logger.debug("+Signal: server_disconnected"))
            self._signals.device_ready.connect(lambda : self._logger.debug("+Signal: device_ready"))
            self._signals.device_disconnected.connect(lambda : self._logger.debug("+Signal: device_disconnected"))
            self._signals.sfd_loaded.connect(lambda : self._logger.debug("+Signal: sfd_loaded"))
            self._signals.sfd_unloaded.connect(lambda : self._logger.debug("+Signal: sfd_unloaded"))
            self._signals.index_changed.connect(lambda : self._logger.debug("+Signal: index_changed"))
            self._signals.datalogging_state_changed.connect(lambda : self._logger.debug("+Signal: datalogging_state_changed"))

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
        self._allow_auto_reconnect = True
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
        
        self._logger.debug("Stopping server manager")
        self._stop_pending = True
        self.signals.stopping.emit()
        
        # Will cause the thread to exit and emit thread_exit_signal that triggers _join_thread_and_emit_stopped in the UI thread
        self._thread_stop_event.set()
        self._client.close_socket()   # Will cancel any pending request in the other thread
        self._logger.debug("Stop initiated")


    def _thread_func(self, config:ServerConfig) -> None:
        """Thread that monitors state change on the server side"""
        self._logger.debug("Server manager thread running")
        self._thread_state.clear()
        
        self._thread_clear_client_events()

        try:
            while not self._thread_stop_event.is_set():
                if self._client.server_state == sdk.ServerState.Disconnected:
                    self._thread_handle_reconnect(config)

                server_state = self._client.server_state
                if server_state == sdk.ServerState.Error:
                    self.stop()
                    break
                self._thread_process_client_events()
                self._thread_handle_download_watchable_logic()

                self._thread_state.last_server_state = server_state
            
        except Exception as e:  # pragma: no cover
            self._logger.critical(f"Error in server manager thread: {e}")
            self._logger.debug(traceback.format_exc())
        finally:
            self._client.disconnect()
            was_connected = self._thread_state.last_server_state == sdk.ServerState.Connected
            if was_connected:
                try:
                    self._signals.server_disconnected.emit()
                except RuntimeError:
                    pass    # May fail if the window is deleted before this thread exits
            
            # Empty the event queue
            self._thread_clear_client_events()

        self._thread_state.clear()
        
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

    def _thread_clear_client_events(self) -> None:
        while self._client.has_event_pending():
            self._client.read_event(timeout=0)

    def _thread_handle_reconnect(self, config:ServerConfig) -> None:
        if self._allow_auto_reconnect and not self._stop_pending:
            # timer to prevent going crazy on function call
            if self._thread_state.connect_timestamp_mono is None or time.monotonic() - self._thread_state.connect_timestamp_mono > self.RECONNECT_DELAY:
                try:
                    self._logger.debug("Connecting client")
                    self._thread_state.connect_timestamp_mono = time.monotonic()
                    self._client.connect(config.hostname, config.port, wait_status=False)
                except sdk.exceptions.ConnectionError:
                    pass


    def _thread_process_client_events(self) -> None:
        while True:
            event = self._client.read_event(timeout=0.2)
            if event is None:
                return
            
            self._logger.debug(f"+Event: {event}")
            if isinstance(event, ScrutinyClient.Events.ConnectedEvent):
                self._signals.server_connected.emit()
                self._clear_index()
                self._allow_auto_reconnect = False    # Ensure we do not try to reconnect until the disconnect event is processed
            elif isinstance(event, ScrutinyClient.Events.DisconnectedEvent):
                self._signals.server_disconnected.emit()
                self._clear_index()
                self._allow_auto_reconnect = True # Full cycle completed. We allow reconencting
            elif isinstance(event, ScrutinyClient.Events.DeviceReadyEvent):
                self._thread_event_device_ready()
            elif isinstance(event, ScrutinyClient.Events.DeviceGoneEvent):
                self._thread_event_device_disconnected()
            elif isinstance(event, ScrutinyClient.Events.SFDLoadedEvent):
                self._thread_event_sfd_loaded()            
            elif isinstance(event, ScrutinyClient.Events.SFDUnLoadedEvent):
                self._thread_event_sfd_unloaded()
            else:
                self._logger.error(f"Unsupported event type : {event.__class__.__name__}")    

    
    def _thread_handle_download_watchable_logic(self) -> None:
        if self._thread_state.runtime_watchables_download_request is not None:
            if self._thread_state.runtime_watchables_download_request.completed:  
                # Download is finished
                # Data is already inside the index. Added from the callback
                was_success = self._thread_state.runtime_watchables_download_request.is_success
                self._thread_state.runtime_watchables_download_request = None   # Clear the request.
                self._logger.debug("Download of watchable list is complete. Group : runtime")
                if was_success:
                    self._signals.index_changed.emit()
                else:
                    self._clear_index_rpv()
            else:
                pass # Downloading
    

        if self._thread_state.sfd_watchables_download_request is not None: 
            if self._thread_state.sfd_watchables_download_request.completed:
                # Download complete
                # Data is already inside the index. Added from the callback
                self._logger.debug("Download of watchable list is complete. Group : SFD")
                was_success = self._thread_state.sfd_watchables_download_request.is_success
                self._thread_state.sfd_watchables_download_request = None    # Clear the request.
                if was_success:
                    self._signals.index_changed.emit()
                else:
                    self._clear_index_alias_var()
            else:
                pass    # Downloading


 
    def _thread_event_device_ready(self) -> None:
        """To be called once when a device connects"""
        self._logger.debug("Detected device ready")
        req = self._thread_state.runtime_watchables_download_request    # Get the ref atomically
        if req is not None:
            req.cancel()
        had_data = self._clear_index(no_changed_event=True) # Event is triggered AFTER device_ready
        self._thread_state.runtime_watchables_download_request = self._client.download_watchable_list(
            types=[sdk.WatchableType.RuntimePublishedValue],
            partial_reception_callback=self._download_data_partial_response_callback
            )
        self._signals.device_ready.emit()
        if had_data:
            self.signals.index_changed.emit()

    def _thread_event_sfd_loaded(self) -> None:
        """To be called once when a SFD is laoded"""
        self._logger.debug("Detected SFD loaded")
        req = self._thread_state.sfd_watchables_download_request    # Get the ref atomically
        if req is not None:
            req.cancel()
        had_data = self._clear_index_alias_var(no_changed_event=True) # Event is triggered AFTER sfd_loaded
        self._thread_state.sfd_watchables_download_request = self._client.download_watchable_list(
            types=[sdk.WatchableType.Variable,sdk.WatchableType.Alias],
            partial_reception_callback=self._download_data_partial_response_callback
            )
        self.signals.sfd_loaded.emit()
        if had_data:
            self.signals.index_changed.emit()

    def _thread_event_sfd_unloaded(self, no_index_event:bool=False) -> None:
        """To be called once when a SFD is unloaded"""
        self._logger.debug("Detected SFD unloaded")
        req = self._thread_state.sfd_watchables_download_request    # Get the ref atomically
        if req is not None:
            req.cancel()
        self._thread_state.sfd_watchables_download_request = None
        self._clear_index_alias_var()   # May trigger index_changed signal
        self.signals.sfd_unloaded.emit()

    def _thread_event_device_disconnected(self) -> None:
        """To be called once when a device disconnect"""
        self._logger.debug("Detected device disconnected")

        req = self._thread_state.runtime_watchables_download_request    # Get the ref atomically
        if req is not None:
            req.cancel()
        self._thread_state.runtime_watchables_download_request = None
        self._clear_index_rpv()   # May trigger index_changed signal
        self.signals.device_disconnected.emit()

    
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
