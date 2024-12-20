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
import enum
from dataclasses import dataclass

from PySide6.QtCore import Signal, QObject
from typing import Optional, Dict, Any, Callable, List, Union, Tuple

from scrutiny.core.logging import DUMPDATA_LOGLEVEL
from scrutiny.gui.core.watchable_registry import WatchableRegistry
from scrutiny.sdk.listeners import BaseListener, ValueUpdate 
from scrutiny.sdk.watchable_handle import WatchableHandle
from scrutiny.tools.profiling import VariableRateExponentialAverager
from scrutiny.tools import format_exception
from scrutiny.core import validation

@dataclass
class ServerConfig:
    hostname:str
    port:int

class QtBufferedListener(BaseListener):
    MAX_SIGNALS_PER_SEC = 15
    TARGET_PROCESS_INTERVAL = 0.2

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
    """Flag preventing overflowing the event loop if the GUI thread is overloaded"""

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

    def ready_for_next_update(self) -> None:
        self.emit_allowed = True
    
    def _emit_signal_if_possible(self) -> None:
        tnow = time.perf_counter_ns()
        tdiff = tnow - self.last_signal_perf_cnt_ns
        expired = tdiff >= self.minimal_inter_signal_delay_ns or tdiff < 0  # Unclear if that counter can wrap. being careful here
        if expired and self.emit_allowed: 
            self.qt_event_rate_measurement.add_data(1)
            self.last_signal_perf_cnt_ns = tnow
            self.emit_allowed = False
            self.signals.data_received.emit()

    def receive(self, updates: List[ValueUpdate]) -> None:
        try:
            self.to_gui_thread_queue.put(updates.copy(), block=False)
        except queue.Full:
            self._logger.error("Dropping an update")

        self._emit_signal_if_possible()
    
    def process(self) -> None:
        # Slow call rate. Called at rate defined by TARGET_PROCESS_INTERVAL
        if self.gui_qsize > 0:
            self._emit_signal_if_possible() # Prune any remaining content if the server stops broadcasting
        self.qt_event_rate_measurement.update()
        
    def allow_subcription_changes_while_running(self) -> bool:
        return True
    
    @property
    def gui_qsize(self) -> int:
        """Return the number of value updates presently stored in the queue linking the listener thread and the QT GUI thread."""
        return self.to_gui_thread_queue.qsize()

    @property
    def effective_event_rate(self) -> float:
        """Returned the measured rate at which the ``data_received`` signal is being emitted"""
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
        listener_event_rate:float

    class WatchableRegistrationState(enum.Enum):
        SUBSCRIBING = enum.auto()
        SUBSCRIBED=enum.auto()
        UNSUBSCRIBING = enum.auto()
        UNSUBSCRIBED=enum.auto()
    
    class WatchablePendingAction(enum.Enum):
        NONE = enum.auto()
        SUBSCRIBE = enum.auto()
        UNSUBSCRIBE = enum.auto()

    @dataclass
    class WatchableRegistrationStatus:
        active_state:"ServerManager.WatchableRegistrationState"
        pending_action:"ServerManager.WatchablePendingAction"
        
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
    _client:ScrutinyClient 
    """The SDK client object that talks with the server"""
    _thread:Optional[threading.Thread] 
    """The thread tyhat runs the synchronous client"""
    _registry:WatchableRegistry 
    """The watchable registry that holds the list of available watchables, downloaded from the server"""

    _thread_stop_event:threading.Event  
    """Event used to stop the thread"""
    _signals:_Signals                   
    """The signals"""
    _internal_signals:_InternalSignals  
    """Some signals used internally, mainly for synchronization"""
    _allow_auto_reconnect:bool          
    """Flag indicating if the thread should try to reconnect the client if disconnected"""
    _logger:logging.Logger              
    """Logger"""
    _thread_state:ThreadState           
    """Data used by the thread to detect state changes"""

    _stop_pending:bool
    """Indicate if a stop is in progress. ``True`` between calls to stop() and emission of ``stopped`` signal"""
    _client_request_store:ClientRequestStore
    """A storage for SDK client request that are scheduled to run in a different thread. See ``schedule_client_request``"""
    _listener : QtBufferedListener
    """A custom listener that passes the data from the SDK client thread to the QT GUI thread"""
    _status_update_received : int
    """Counter that tells how many status update we received"""

    _registration_status_store:Dict[sdk.WatchableType, Dict[str, WatchableRegistrationStatus]]
    """A dictionnary tha tmaps servepath to a subscribtion status. Used to deal with request for subscription happening while another is not complete."""

    _unit_test:bool
    """Enable some internal instrumentation for unit testing"""
    _watch_unwatch_ui_callback_call_count:int
    """For unit testing. USed for synchronization of threads"""
    _exit_in_progress:bool
    """Flag set by the main window informing that the application is exiting. Cancel callbacks"""

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

        # Registration logic
        self._registration_status_store = {
            sdk.WatchableType.Variable:{},
            sdk.WatchableType.Alias:{},
            sdk.WatchableType.RuntimePublishedValue:{}
        }

        def clear_rpv_registration_status() -> None:
            self._registration_status_store[sdk.WatchableType.RuntimePublishedValue].clear()
        def clear_var_alias_registration_status() -> None:
            self._registration_status_store[sdk.WatchableType.Variable].clear()
            self._registration_status_store[sdk.WatchableType.RuntimePublishedValue].clear()
        def clear_all_registration_status() -> None:
            for k in self._registration_status_store:
                self._registration_status_store[k].clear()

        self._signals.device_disconnected.connect(clear_rpv_registration_status)
        self._signals.sfd_unloaded.connect(clear_var_alias_registration_status)
        self._signals.server_connected.connect(clear_all_registration_status)
        self._signals.server_disconnected.connect(clear_all_registration_status)

        self._unit_test = False
        self._watch_unwatch_ui_callback_call_count = 0
        self._exit_in_progress = False

        # Logging logic
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
        """Called when the stop process is completed. Triggered by the internal thread, executed in the QT thread"""
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
        # Called from the QT thread
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
        # Called from the QT thread + Server thread
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
        # Is the server thread
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
                    self.stop()      # Race conditon?
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
        # Called from internal thread
        while self._client.has_event_pending():
            self._client.read_event(timeout=0)

    def _thread_handle_reconnect(self, config:ServerConfig) -> None:
        # Called from internal thread
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
        # Called from internal thread
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
        # Called from internal thread 
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
        """Removed everything from the watchable registry. Also clear the subscribe/unsubscribe states of each watched item"""
        had_data = self._registry.clear()
        if had_data and not no_changed_event:
            self.signals.registry_changed.emit()
        return had_data
    
    def _clear_registry_alias_var(self, no_changed_event:bool=False) -> bool:
        """Removed Alias and Variables from the watchable registry. Also clear the subscribe/unsubscribe states of each watched item of those types"""
        had_data_alias = self._registry.clear_content_by_type(sdk.WatchableType.Alias)
        had_data_var = self._registry.clear_content_by_type(sdk.WatchableType.Variable)
        had_data = had_data_var or had_data_alias
        if had_data and not no_changed_event:
            self.signals.registry_changed.emit()
        return had_data
    
    def _clear_registry_rpv(self, no_changed_event:bool=False) -> bool:
        """Removed RuntimePublishedValues from the watchable registry. Also clear the subscribe/unsubscribe states of each watched item of those types"""
        had_data = self._registry.clear_content_by_type(sdk.WatchableType.RuntimePublishedValue)
        if had_data and not no_changed_event:
            self.signals.registry_changed.emit()
        return had_data

    def _watch_unwatch_ui_callback(self,
                                   new_state:WatchableRegistrationState,
                                   watchable_type:sdk.WatchableType,
                                   server_path:str, 
                                   registration_status:WatchableRegistrationStatus, 
                                   handle:Optional[WatchableHandle]) -> None:
        registration_status.active_state = new_state
        if handle is not None:
            self._listener.subscribe(handle)
        
        if (registration_status.active_state == self.WatchableRegistrationState.UNSUBSCRIBED 
            and registration_status.pending_action==self.WatchablePendingAction.NONE):
            if server_path in self._registration_status_store[watchable_type]:
                del self._registration_status_store[watchable_type][server_path]
        else:
            if registration_status.pending_action == self.WatchablePendingAction.SUBSCRIBE:
                self._maybe_request_watch(watchable_type, server_path)
            elif registration_status.pending_action == self.WatchablePendingAction.UNSUBSCRIBE:
                self._maybe_request_unwatch(watchable_type, server_path)

        if self._unit_test:
            self._watch_unwatch_ui_callback_call_count+=1

    def _anonymous_thread_process_watch_request(self, server_path:str,client:ScrutinyClient) -> Tuple[WatchableRegistrationState, Optional[WatchableHandle]]:
        new_state = self.WatchableRegistrationState.SUBSCRIBED
        handle:Optional[WatchableHandle] = None
        try:
            handle = client.watch(server_path)
        except sdk.exceptions.ScrutinySDKException as e:
            self._logger.error(f"Failed to watch {server_path}. {e}")
            new_state = self.WatchableRegistrationState.UNSUBSCRIBED
        
        return (new_state, handle)

    def _anonymous_thread_process_unwatch_request(self, server_path:str, client:ScrutinyClient) -> WatchableRegistrationState:
        new_state = self.WatchableRegistrationState.UNSUBSCRIBED
        success = False
        try:
            client.unwatch(server_path)
            success = True
        except sdk.exceptions.ScrutinySDKException as e:
            # Abnormal only if the server is present. otherwise we expect a failure.
            if client.server_state == sdk.ServerState.Connected:
                self._logger.error(f"Failed to unwatch {server_path}. {e}")
        
        if not success:
            handle = client.try_get_existing_watch_handle(server_path)
            if handle is not None and not handle._is_dead():
                new_state = self.WatchableRegistrationState.SUBSCRIBED

        return new_state
        

    def _maybe_request_watch(self, watchable_type:sdk.WatchableType, server_path:str) -> None:
        """Will request the server for a watch subscription if not already done or working on it."""
        if not server_path in self._registration_status_store[watchable_type]:
            self._registration_status_store[watchable_type][server_path] = self.WatchableRegistrationStatus(
                active_state=self.WatchableRegistrationState.UNSUBSCRIBED,
                pending_action=self.WatchablePendingAction.NONE
            )
        registration_status = self._registration_status_store[watchable_type][server_path]
        
        if registration_status.active_state in [self.WatchableRegistrationState.SUBSCRIBED, self.WatchableRegistrationState.SUBSCRIBING]:
            # Nothing to do. Ensure we do nothing
            registration_status.pending_action = self.WatchablePendingAction.NONE
        elif registration_status.active_state == self.WatchableRegistrationState.UNSUBSCRIBING:
            # enqueue. Existing thread will pick this up
            registration_status.pending_action = self.WatchablePendingAction.SUBSCRIBE
        elif registration_status.active_state == self.WatchableRegistrationState.UNSUBSCRIBED:
            # Proceed with subscription
            registration_status.pending_action = self.WatchablePendingAction.NONE
            registration_status.active_state = self.WatchableRegistrationState.SUBSCRIBING
            def func(client:ScrutinyClient) -> Tuple[ServerManager.WatchableRegistrationState, Optional[WatchableHandle]]:
                return self._anonymous_thread_process_watch_request(server_path=server_path, client=client)

            def ui_callback(return_val:Optional[Tuple[ServerManager.WatchableRegistrationState, Optional[WatchableHandle]]], exception:Optional[Exception]) -> None:
                if exception is not None:
                    self._logger.critical(str(exception))
                    if self._logger.isEnabledFor(logging.DEBUG):    # pragma: no cover
                        self._logger.debug(format_exception(exception))
                else:
                    assert return_val is not None
                    new_state, handle = return_val

                    self._watch_unwatch_ui_callback(
                        new_state = new_state,
                        watchable_type=watchable_type, 
                        server_path=server_path, 
                        registration_status=registration_status, 
                        handle=handle)

            self.schedule_client_request(func, ui_callback)
        else:   # pragma: no cover
            raise NotImplementedError(f"Unsupported state: {registration_status.active_state}")

    def _maybe_request_unwatch(self, watchable_type:sdk.WatchableType, server_path:str) -> None:
        """Will request the server to unsubscribe to a watchif not already done or working on it."""
        if not server_path in self._registration_status_store[watchable_type]:
            self._registration_status_store[watchable_type][server_path] = self.WatchableRegistrationStatus(
                active_state=self.WatchableRegistrationState.UNSUBSCRIBED,
                pending_action=self.WatchablePendingAction.NONE
            )
        registration_status = self._registration_status_store[watchable_type][server_path]
        
        if registration_status.active_state in [self.WatchableRegistrationState.UNSUBSCRIBED, self.WatchableRegistrationState.UNSUBSCRIBING]:
            # Nothing to do. Ensure we do nothing
            registration_status.pending_action = self.WatchablePendingAction.NONE
        elif registration_status.active_state == self.WatchableRegistrationState.SUBSCRIBING:
            # enqueue. Existing thread will pick this up
            registration_status.pending_action = self.WatchablePendingAction.UNSUBSCRIBE
        elif registration_status.active_state == self.WatchableRegistrationState.SUBSCRIBED:
            # Proceed with unsubscription
            registration_status.pending_action = self.WatchablePendingAction.NONE
            registration_status.active_state = self.WatchableRegistrationState.UNSUBSCRIBING
            def func(client:ScrutinyClient) -> ServerManager.WatchableRegistrationState:
                return self._anonymous_thread_process_unwatch_request(server_path=server_path, client=client)

            def ui_callback(new_state:Optional[ServerManager.WatchableRegistrationState], exception:Optional[Exception]) -> None:
                if exception is not None:
                    self._logger.critical(str(exception))
                    if self._logger.isEnabledFor(logging.DEBUG):    # pragma: no cover
                        self._logger.debug(format_exception(exception))
                else:
                    assert new_state is not None

                    self._watch_unwatch_ui_callback(
                        new_state=new_state,
                        watchable_type=watchable_type, 
                        server_path=server_path, 
                        registration_status=registration_status, 
                        handle=None)

            self.schedule_client_request(func,ui_callback)
        else:   # pragma: no cover
            raise NotImplementedError(f"Unsupported state: {registration_status.active_state}")

    def _registry_watch_callback(self, watcher_id:Union[str,int], server_path:str, watchable_config:sdk.WatchableConfiguration) -> None:
        """Called when a gui component register a watcher on the registry"""
        # Runs from QT thread
        watcher_count = self._registry.node_watcher_count(watchable_config.watchable_type, server_path)
        if watcher_count > 0:
            self._maybe_request_watch(watchable_config.watchable_type, server_path)

    def _registry_unwatch_callback(self, watcher_id:Union[str,int], server_path:str, watchable_config:sdk.WatchableConfiguration) -> None:
        """Called when a gui component unregister a watcher on the registry"""
        # Runs from QT thread
        watcher_count = self._registry.node_watcher_count(watchable_config.watchable_type, server_path)
        if watcher_count == 0:
            self._maybe_request_unwatch(watchable_config.watchable_type, server_path)

    def _value_update_received(self) -> None:
        # Called in the QT thread when a value update is received by the lsitener (the client)
        aggregated_updates:List[ValueUpdate] = []
        while not self._listener.to_gui_thread_queue.empty():
            update_list = self._listener.to_gui_thread_queue.get_nowait()
            aggregated_updates.extend(update_list)

        self._registry.broadcast_value_updates_to_watchers(aggregated_updates)
        self._listener.ready_for_next_update()
 
    def get_server_state(self) -> sdk.ServerState:
        # Called from QT thread + Server thread. atomic
        return self._client.server_state
    
    def get_server_info(self) -> Optional[sdk.ServerInfo]:
        # Called from QT thread + Server thread. atomic
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
        if entry is None:
            self._logger.debug("Client request compelted, but entry not part of the store.")
            return 
    
        if self._exit_in_progress:
            # Prevents weird behavior on app exit, like accessing deleted resources
            # The main window is expected to call exit() before exiting.
            self._logger.debug("Client request completed, but the server manager has been stopped. Ignoring.")
            return  
        
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

            if self._exit_in_progress:
                return 
            
            # A race condition is possible here when exiting the application
            # Resources can be deleted between here and the end.

            entry = ClientRequestStore.ClientRequestEntry(
                ui_callback=ui_thread_callback,
                threaded_func_return_value=return_val,
                error=error
            )
            assigned_id = self._client_request_store.register(entry)
            try:
                self._internal_signals.client_request_completed.emit(assigned_id)
            except Exception as e:
                # Expected to fail if QT has deleted internal resources
                if not self._exit_in_progress:
                    self._logger.error(f"Failed to emit client_request_completed signal. {e}")

        t = threading.Thread(target=threaded_func, daemon=True)
        t.start()

    def get_stats(self) -> Statistics:
        """Return some internal metrics for diagnostic"""
        return self.Statistics(
            listener=self._listener.get_stats(),
            client=self._client.get_local_stats(),
            watchable_registry=self._registry.get_stats(),
            listener_to_gui_qsize=self._listener.gui_qsize,
            listener_event_rate=self._listener.effective_event_rate,
            status_update_received=self._status_update_received
        )
    
    def reset_stats(self) -> None:
        self._listener.reset_stats()
        self._client.reset_local_stats()
        self._status_update_received = 0

    def exit(self)->None:
        self.stop()
        self._exit_in_progress = True

   
    def write_watchable_value(self, fqn:str, value:Union[str, int, float, bool], callback:Callable[[Optional[Exception]], None]) -> None:
        def threaded_func(client:ScrutinyClient) -> None:
            watchable_config = self.registry.get_watchable_fqn(fqn)
            handle = client.try_get_existing_watch_handle_by_server_id(watchable_config.server_id)
            if handle is None:
                raise Exception(f"Item {fqn} is not being watched. Cannot write its value")
            
            if isinstance(value, str):
                handle.write_value_str(value)  # Defer data parsing to the server
            else:
                handle.value = value
                
        def ui_callback(_:None, exception:Optional[Exception]) -> None:
            callback(exception)

        self.schedule_client_request(threaded_func, ui_callback)
