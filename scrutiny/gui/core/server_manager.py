#    server_manager.py
#        Object that handles the communication with the server and inform the rest of the
#         GUI about what's happening on the other side of the socket. Based on the SDK ScrutinyClient
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['ServerManager', 'ServerConfig', 'ValueUpdate', 'Statistics']

from scrutiny import sdk
from scrutiny.sdk.client import ScrutinyClient, WatchableListDownloadRequest
import threading
import time
import traceback
import logging
import queue
from dataclasses import dataclass

from PySide6.QtCore import Signal, QObject
from typing import Optional, Dict, Any, Callable, List, Union

from scrutiny.core.logging import DUMPDATA_LOGLEVEL
from scrutiny.gui.core.watchable_registry import WatchableRegistry
from scrutiny.sdk.listeners import BaseListener, ValueUpdate 
from scrutiny.sdk.watchable_handle import WatchableHandle
from scrutiny.tools.profiling import VariableRateExponentialAverager
@dataclass
class ServerConfig:
    hostname:str
    port:int

class QtBufferedListener(BaseListener):
    MAX_SIGNALS_PER_SEC = 15

    class _Signals(QObject):
        data_received = Signal()
    
    to_gui_thread_queue:"queue.Queue[List[ValueUpdate]]"
    """A queue to transfer the value updates to the GUI thread"""
    signals:_Signals
    """The signals that this listener can emit"""
    last_signal_perf_cnt_ns:int
    """Timestamp of the last signal being sent"""
    minimal_inter_signal_delay_ns:int = int(1e9/MAX_SIGNALS_PER_SEC)
    """Minimal amount of time between two data_received signals"""
    emit_allowed:bool
    """Flag preventing overflowing the event loop if the GUI thread is overlkaded"""

    def __init__(self, *args:Any, **kwargs:Any):
        BaseListener.__init__(self, *args, **kwargs)
        self.to_gui_thread_queue = queue.Queue(maxsize=1000)
        self.signals = self._Signals()
        self.last_signal_perf_cnt_ns  = time.perf_counter_ns()
        self.emit_allowed = True
        self.qt_event_rate_measurement = VariableRateExponentialAverager(time_estimation_window=0.1, tau=0.5, near_zero=0.1)
    
    def setup(self) -> None:
        self.qt_event_rate_measurement.enable()
    
    def teardown(self) -> None:
        self.qt_event_rate_measurement.disable()

    def ready_for_next_update(self):
        self.emit_allowed = True
    
    def receive(self, updates: List[ValueUpdate]) -> None:
        try:
            self.to_gui_thread_queue.put(updates.copy(), block=False)
        except queue.Full:
            self._logger.error("Dropping an update")

        tnow = time.perf_counter_ns()
        tdiff = tnow - self.last_signal_perf_cnt_ns
        expired = tdiff >= self.minimal_inter_signal_delay_ns or tdiff < 0  # Unclear if that counter can wrap. being careful here
        if expired and self.emit_allowed: 
            self.qt_event_rate_measurement.add_data(1)
            self.last_signal_perf_cnt_ns = tnow
            self.emit_allowed = False
            self.signals.data_received.emit()
    
    def process(self):
        self.qt_event_rate_measurement.update()

    def allow_subcription_changes_while_running(self) -> bool:
        return True
    

    @property
    def gui_qsize(self) -> int:
        """Return the number of value updates presently stored in the queue linking the listener thread and the QT GUI thread."""
        return self.to_gui_thread_queue.qsize()

    @property
    def get_effective_event_rate(self) -> float:
        return self.qt_event_rate_measurement.get_value()

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

    @dataclass(frozen=True)
    class Statistics:
        listener: BaseListener.Statistics
        client:ScrutinyClient.Statistics
        watchable_registry:WatchableRegistry.Statistics
        status_update_received:int
        listener_to_gui_qsize:int
        listener_event_rate:int

        
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
        registry_changed = Signal()
        status_received = Signal()

    RECONNECT_DELAY = 1
    _client:ScrutinyClient              # The SDK client object that talks with the server
    _thread:Optional[threading.Thread]  # The thread tyhat runs the synchronous client
    _registry:WatchableRegistry         # The watchable registry that holds the list of available watchables, downloaded from the server

    _thread_stop_event:threading.Event  # Event used to stop the thread
    _signals:_Signals                   # The signals
    _internal_signals:_InternalSignals  # Some signals used internally, mainly for synchronization
    _allow_auto_reconnect:bool          # Flag indicating if the thread should try to reconnect the client if disconnected
    _logger:logging.Logger              # Logger
    _thread_state:ThreadState           # Data used by the thread to detect state changes

    _stop_pending:bool
    _client_request_store:ClientRequestStore
    _listener : QtBufferedListener
    _status_update_received : int

    def __init__(self, watchable_registry:WatchableRegistry, client:Optional[ScrutinyClient]=None) -> None:
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
        self._registry = watchable_registry

        self._internal_signals.thread_exit_signal.connect(self._join_thread_and_emit_stopped)
        self._internal_signals.client_request_completed.connect(self._client_request_completed)
        self._stop_pending = False
        self._client_request_store = ClientRequestStore()
        self.registry.register_global_watch_callback(self._registry_watch_callback, self._registry_unwatch_callback)

        self._listener = QtBufferedListener()
        self._client.register_listener(self._listener)
        self._listener.signals.data_received.connect(self._value_update_received)

        self._status_update_received = 0
        def inc_status_update_count() -> None:
            self._status_update_received += 1
        self._signals.status_received.connect(inc_status_update_count)

        if self._logger.isEnabledFor(DUMPDATA_LOGLEVEL):    # pragma: no cover
            self._signals.server_connected.connect(lambda : self._logger.log(DUMPDATA_LOGLEVEL, "+Signal: server_connected"))
            self._signals.server_disconnected.connect(lambda : self._logger.log(DUMPDATA_LOGLEVEL, "+Signal: server_disconnected"))
            self._signals.device_ready.connect(lambda : self._logger.log(DUMPDATA_LOGLEVEL, "+Signal: device_ready"))
            self._signals.device_disconnected.connect(lambda : self._logger.log(DUMPDATA_LOGLEVEL, "+Signal: device_disconnected"))
            self._signals.sfd_loaded.connect(lambda : self._logger.log(DUMPDATA_LOGLEVEL, "+Signal: sfd_loaded"))
            self._signals.sfd_unloaded.connect(lambda : self._logger.log(DUMPDATA_LOGLEVEL, "+Signal: sfd_unloaded"))
            self._signals.registry_changed.connect(lambda : self._logger.log(DUMPDATA_LOGLEVEL, "+Signal: registry_changed"))
            self._signals.datalogging_state_changed.connect(lambda : self._logger.log(DUMPDATA_LOGLEVEL, "+Signal: datalogging_state_changed"))
            self._signals.status_received.connect(lambda : self._logger.log(DUMPDATA_LOGLEVEL, "+Signal: status_received"))

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
    def registry(self) -> WatchableRegistry:
        """The watchable registry containing a definition of all the watchables available on the server"""
        return self._registry

    
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
        self._listener.reset_stats()
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
            self._listener.start()
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
        self._listener.stop()
        self._listener.unsubscribe_all()
        
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
            
            self._logger.log(DUMPDATA_LOGLEVEL, f"+Event: {event}")
            if isinstance(event, ScrutinyClient.Events.ConnectedEvent):
                self._signals.server_connected.emit()
                self._clear_registry()
                self._allow_auto_reconnect = False    # Ensure we do not try to reconnect until the disconnect event is processed
            elif isinstance(event, ScrutinyClient.Events.DisconnectedEvent):
                self._signals.server_disconnected.emit()
                self._clear_registry()
                self._allow_auto_reconnect = True # Full cycle completed. We allow reconnecting
            elif isinstance(event, ScrutinyClient.Events.DeviceReadyEvent):
                self._thread_event_device_ready()
            elif isinstance(event, ScrutinyClient.Events.DeviceGoneEvent):
                self._thread_event_device_disconnected()
            elif isinstance(event, ScrutinyClient.Events.SFDLoadedEvent):
                self._thread_event_sfd_loaded()            
            elif isinstance(event, ScrutinyClient.Events.SFDUnLoadedEvent):
                self._thread_event_sfd_unloaded()
            elif isinstance(event, ScrutinyClient.Events.DataloggerStateChanged):
                self._signals.datalogging_state_changed.emit()
            elif isinstance(event, ScrutinyClient.Events.StatusUpdateEvent):
                self._signals.status_received.emit()
            else:
                self._logger.error(f"Unsupported event type : {event.__class__.__name__}")    

    def _thread_handle_download_watchable_logic(self) -> None:
        if self._thread_state.runtime_watchables_download_request is not None:
            if self._thread_state.runtime_watchables_download_request.completed:  
                # Download is finished
                # Data is already inside the registry. Added from the callback
                was_success = self._thread_state.runtime_watchables_download_request.is_success
                self._thread_state.runtime_watchables_download_request = None   # Clear the request.
                self._logger.debug("Download of watchable list is complete. Group : runtime")
                if was_success:
                    self._signals.registry_changed.emit()
                else:
                    self._clear_registry_rpv()
            else:
                pass # Downloading
    

        if self._thread_state.sfd_watchables_download_request is not None: 
            if self._thread_state.sfd_watchables_download_request.completed:
                # Download complete
                # Data is already inside the registry. Added from the callback
                self._logger.debug("Download of watchable list is complete. Group : SFD")
                was_success = self._thread_state.sfd_watchables_download_request.is_success
                self._thread_state.sfd_watchables_download_request = None    # Clear the request.
                if was_success:
                    self._signals.registry_changed.emit()
                else:
                    self._clear_registry_alias_var()
            else:
                pass    # Downloading

    def _thread_event_device_ready(self) -> None:
        """To be called once when a device connects"""
        self._logger.debug("Detected device ready")
        req = self._thread_state.runtime_watchables_download_request    # Get the ref atomically
        if req is not None:
            req.cancel()
        had_data = self._clear_registry(no_changed_event=True) # Event is triggered AFTER device_ready
        self._thread_state.runtime_watchables_download_request = self._client.download_watchable_list(
            types=[sdk.WatchableType.RuntimePublishedValue],
            partial_reception_callback=self._download_data_partial_response_callback
            )
        self._signals.device_ready.emit()
        if had_data:
            self.signals.registry_changed.emit()

    def _thread_event_sfd_loaded(self) -> None:
        """To be called once when a SFD is laoded"""
        self._logger.debug("Detected SFD loaded")
        req = self._thread_state.sfd_watchables_download_request    # Get the ref atomically
        if req is not None:
            req.cancel()
        had_data = self._clear_registry_alias_var(no_changed_event=True) # Event is triggered AFTER sfd_loaded
        self._thread_state.sfd_watchables_download_request = self._client.download_watchable_list(
            types=[sdk.WatchableType.Variable,sdk.WatchableType.Alias],
            partial_reception_callback=self._download_data_partial_response_callback
            )
        self.signals.sfd_loaded.emit()
        if had_data:
            self.signals.registry_changed.emit()

    def _thread_event_sfd_unloaded(self) -> None:
        """To be called once when a SFD is unloaded"""
        self._logger.debug("Detected SFD unloaded")
        req = self._thread_state.sfd_watchables_download_request    # Get the ref atomically
        if req is not None:
            req.cancel()
        self._thread_state.sfd_watchables_download_request = None
        self._clear_registry_alias_var()   # May trigger registry_changed signal
        self.signals.sfd_unloaded.emit()

    def _thread_event_device_disconnected(self) -> None:
        """To be called once when a device disconnect"""
        self._logger.debug("Detected device disconnected")

        req = self._thread_state.runtime_watchables_download_request    # Get the ref atomically
        if req is not None:
            req.cancel()
        self._thread_state.runtime_watchables_download_request = None
        self._clear_registry_rpv()   # May trigger registry_changed signal
        self.signals.device_disconnected.emit()

    def _download_data_partial_response_callback(self, 
        data:Dict[sdk.WatchableType, Dict[str, sdk.WatchableConfiguration]], 
        last_segment:bool) -> None:
        # This method is called from within the client internal worker thread
        # Qt signals are thread safe.

        if self._logger.isEnabledFor(logging.DEBUG):    # pragma: no cover
            stats = dict(zip([x.name for x in data.keys()], [len(x) for x in data.values()]))
            self._logger.debug(f"Received data. Count {stats}")

        self._registry.add_content(data)   # Thread safe method
        if last_segment:
            self._logger.debug("Finished downloading watchable list")

    def _clear_registry(self, no_changed_event:bool=False) -> bool:
        had_data = self._registry.clear()
        if had_data and not no_changed_event:
            self.signals.registry_changed.emit()
        return had_data
    
    def _clear_registry_alias_var(self, no_changed_event:bool=False) -> bool:
        had_data_alias = self._registry.clear_content_by_type(sdk.WatchableType.Alias)
        had_data_var = self._registry.clear_content_by_type(sdk.WatchableType.Variable)
        had_data = had_data_var or had_data_alias
        if had_data and not no_changed_event:
            self.signals.registry_changed.emit()
        return had_data
    
    def _clear_registry_rpv(self, no_changed_event:bool=False) -> bool:
        had_data = self._registry.clear_content_by_type(sdk.WatchableType.RuntimePublishedValue)
        if had_data and not no_changed_event:
            self.signals.registry_changed.emit()
        return had_data

    def _registry_watch_callback(self, watcher_id:Union[str,int], display_path:str, watchable_config:sdk.WatchableConfiguration) -> None:
        """Called when a gui component register a watcher on the registry"""
        watcher_count = self._registry.node_watcher_count(watchable_config.watchable_type, display_path)
        if watcher_count == 1:
            def func(client:ScrutinyClient) -> WatchableHandle:
                # Runs in a separate thread. 
                return client.watch(display_path)   # Blocks until a response is received

            def finish_callback(handle:Optional[WatchableHandle], exception:Optional[Exception]) -> None:
                # Runs in the GUI thread
                if handle is not None and self._listener.is_started:
                    self._listener.subscribe(handle)
                if exception:
                    self._logger.warning(str(exception))
                    self._logger.debug(traceback.format_exc())
            self.schedule_client_request(func, finish_callback)

    def _registry_unwatch_callback(self, watcher_id:Union[str,int], display_path:str, watchable_config:sdk.WatchableConfiguration) -> None:
        """Called when a gui component unregister a watcher on the registry"""
        # This runs from the GUI thread
        watcher_count = self._registry.node_watcher_count(watchable_config.watchable_type, display_path)
        if watcher_count == 0:
            handle = self._client.try_get_existing_watch_handle(display_path)
            if handle is not None:
                def func(client:ScrutinyClient) -> None:
                    # Runs in a separate thread.
                    handle.unwatch()    # Blocks until a response is received

                def finish_callback(result:None, exception:Optional[Exception]) -> None:
                    # Runs in the GUI thread
                    pass
                self.schedule_client_request(func, finish_callback)

    def _value_update_received(self) -> None:
        # Called in the GUI thread when a value update is received by the lsitener (the client)
        aggregated_updates:List[ValueUpdate] = []
        while not self._listener.to_gui_thread_queue.empty():
            update_list = self._listener.to_gui_thread_queue.get_nowait()
            aggregated_updates.extend(update_list)

        self._registry.broadcast_value_updates_to_watchers(aggregated_updates)
        self._listener.ready_for_next_update()
 
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
        """Runs a client request in a separate thread and calls a callback in the UI thread when done."""

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

    def get_stats(self) -> Statistics:
        return self.Statistics(
            listener=self._listener.get_stats(),
            client=self._client.get_stats(),
            watchable_registry=self._registry.get_stats(),
            listener_to_gui_qsize=self._listener.gui_qsize,
            listener_event_rate=self._listener.get_effective_event_rate,
            status_update_received=self._status_update_received
        )
