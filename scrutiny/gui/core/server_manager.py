#    server_manager.py
#        Object that handles the communication with the server and inform the rest of the
#         GUI about what's happening on the other side of the socket. Based on the SDK ScrutinyClient
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['ServerManager', 'ServerConfig', 'ValueUpdate', 'Statistics']

from scrutiny import sdk
from scrutiny.sdk.client import ScrutinyClient, WatchableListDownloadRequest
import threading
import time
import logging
import queue
import enum
from copy import copy
from dataclasses import dataclass
from scrutiny.tools.thread_enforcer import thread_func, enforce_thread
from scrutiny import tools

from PySide6.QtCore import Signal, QObject
from typing import Optional, Dict, Any, Callable, List, Union, cast, Tuple

from scrutiny.core.logging import DUMPDATA_LOGLEVEL
from scrutiny.gui.core.watchable_registry import WatchableRegistry
from scrutiny.gui.core.user_messages_manager import UserMessagesManager
from scrutiny.sdk.listeners import BaseListener, ValueUpdate 
from scrutiny.sdk.watchable_handle import WatchableHandle
from scrutiny.tools.profiling import VariableRateExponentialAverager
from scrutiny.gui.core.threads import QT_THREAD_NAME, SERVER_MANAGER_THREAD_NAME
from scrutiny.gui.tools.invoker import InvokeInQtThreadSynchronized, InvokeQueued

USER_MSG_ID_CONNECT_FAILED = "connect_failed"
USER_MSG_UPDATE_OVERRUN = "listener_update_dropped"

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
    update_dropped_count:int
    """A counter that keeps track of how many value updates were lost during this session"""
    _last_drop_message_monotonic_time:Optional[float]
    """A timestamp used to avoid spamming the logger/messaging system when the queue overflows"""

    def __init__(self, *args:Any, **kwargs:Any):
        BaseListener.__init__(self, *args, **kwargs)
        self.to_gui_thread_queue = queue.Queue(maxsize=1000)    # Full load test peaks at 50
        self.signals = self._Signals()
        self.last_signal_perf_cnt_ns  = time.perf_counter_ns()
        self.emit_allowed = True
        self.qt_event_rate_measurement = VariableRateExponentialAverager(time_estimation_window=0.1, tau=0.5, near_zero=0.1)
        self.update_dropped_count = 0
        self._last_drop_message_monotonic_time = None
    
    def setup(self) -> None:
        self.update_dropped_count = 0
        self.qt_event_rate_measurement.enable()
        self.emit_allowed=True
    
    def teardown(self) -> None:
        self.emit_allowed = False
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
            self.update_dropped_count += 1
            if self._last_drop_message_monotonic_time is None or time.monotonic() - self._last_drop_message_monotonic_time > 1:
                msg = f"Value update overrun. Total lost: {self.update_dropped_count} updates"
                self._logger.error(msg)
                UserMessagesManager.instance().register_message_thread_safe(USER_MSG_UPDATE_OVERRUN, msg , 3)
                self._last_drop_message_monotonic_time = time.monotonic()

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
        SUBSCRIBED = enum.auto()
        UNSUBSCRIBING = enum.auto()
        UNSUBSCRIBED = enum.auto()

        def is_transition_state(self) -> bool:
            return self in cast(List[ServerManager.WatchableRegistrationState], [self.SUBSCRIBING, self.UNSUBSCRIBING])
    
    class WatchableRegistrationAction(enum.Enum):
        NONE = enum.auto()
        SUBSCRIBE = enum.auto()
        UNSUBSCRIBE = enum.auto()

    @dataclass
    class WatchableRegistrationStatus:
        active_state:"ServerManager.WatchableRegistrationState"
        pending_action:"ServerManager.WatchableRegistrationAction"
        
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
        device_info_availability_changed = Signal()
        loaded_sfd_availability_changed = Signal()
        datalogging_storage_updated = Signal(sdk.DataloggingListChangeType, str)  # type, refernece_id

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
    _qt_watch_unwatch_ui_callback_call_count:int
    """For unit testing. Used for synchronization of threads"""
    _exit_in_progress:bool
    """Flag set by the main window informing that the application is exiting. Cancel callbacks"""

    _device_info: Optional[sdk.DeviceInfo]
    """Contains all the info about the actually connected device. ``None`` if not available"""
    _loaded_sfd: Optional[sdk.SFDInfo]
    """Contains all the info about the actually loaded Scrutiny Firmware Description. ``None`` if not available"""

    _partial_watchable_downloaded_data:Dict[sdk.WatchableType, Dict[str, sdk.WatchableConfiguration]]

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
        self._partial_watchable_downloaded_data = {
            sdk.WatchableType.Variable:{},
            sdk.WatchableType.Alias:{},
            sdk.WatchableType.RuntimePublishedValue:{}
        }

        self._internal_signals.thread_exit_signal.connect(self._qt_thread_join_thread_and_emit_stopped)
        self._internal_signals.client_request_completed.connect(self._qt_client_request_completed)
        self._stop_pending = False
        self._client_request_store = ClientRequestStore()
        self._registry.register_global_watch_callback(self._qt_registry_watch_callback, self._qt_registry_unwatch_callback)

        self._listener = QtBufferedListener()
        self._client.register_listener(self._listener)
        self._listener.signals.data_received.connect(self._qt_value_update_received)

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
        self._qt_watch_unwatch_ui_callback_call_count = 0
        self._exit_in_progress = False

        self._device_info = None
        self._loaded_sfd = None

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
            self._signals.device_info_availability_changed.connect(lambda : self._logger.log(DUMPDATA_LOGLEVEL, "+Signal: device_info_availability_changed"))
            self._signals.loaded_sfd_availability_changed.connect(lambda : self._logger.log(DUMPDATA_LOGLEVEL, "+Signal: loaded_sfd_availability_changed"))
            self._signals.datalogging_storage_updated.connect(lambda : self._logger.log(DUMPDATA_LOGLEVEL, "+Signal: datalogging_storage_updated"))
        
        
        # These internal slots are used to download the device info and SFD details when they are ready
        self._signals.sfd_loaded.connect(self._sfd_loaded_callback)
        self._signals.sfd_unloaded.connect(self._sfd_unloaded_callback)
        self._signals.device_ready.connect(self._device_ready_callback)
        self._signals.device_disconnected.connect(self._device_disconnected_callback)
        self._signals.server_disconnected.connect(self._server_disconnected_callback)


    #region Private - internal thread    

    @thread_func(SERVER_MANAGER_THREAD_NAME)
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
                    InvokeInQtThreadSynchronized(self.stop)
                    break
                self._thread_process_client_events()
                self._thread_handle_download_watchable_logic()

                self._thread_state.last_server_state = server_state
            
        except Exception as e:  # pragma: no cover
            if not self._exit_in_progress:
                str_level = logging.CRITICAL
                traceback_level = logging.INFO
            else:
                str_level = logging.DEBUG
                traceback_level = logging.DEBUG
            tools.log_exception(self._logger, e, "Error in server manager thread", str_level=str_level, traceback_level=traceback_level)
        finally:
            self._client.disconnect()
            was_connected = self._thread_state.last_server_state == sdk.ServerState.Connected
            if was_connected:
                with tools.SuppressException(RuntimeError): # May fail if the window is deleted before this thread exits
                    self._signals.server_disconnected.emit()
            
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
        with tools.SuppressException(RuntimeError): # May fail if the window is deleted before this thread exits
            self._internal_signals.thread_exit_signal.emit()

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
                    UserMessagesManager.instance().clear_message_thread_safe(USER_MSG_ID_CONNECT_FAILED)
                except sdk.exceptions.ConnectionError as e:
                    if not self.is_stopping():
                        UserMessagesManager.instance().register_message_thread_safe(USER_MSG_ID_CONNECT_FAILED, str(e), 5)

    def _thread_process_client_events(self) -> None:
        # Called from internal thread
        while True:
            event = self._client.read_event(timeout=0.2)
            if event is None:
                return
            
            self._logger.log(DUMPDATA_LOGLEVEL, f"+Event: {event}")
            if isinstance(event, ScrutinyClient.Events.ConnectedEvent):
                changed = InvokeInQtThreadSynchronized(self._registry.clear, timeout=2)
                self._signals.server_connected.emit()
                if changed:
                    self.signals.registry_changed.emit()
                self._allow_auto_reconnect = False    # Ensure we do not try to reconnect until the disconnect event is processed
            elif isinstance(event, ScrutinyClient.Events.DisconnectedEvent):
                changed = InvokeInQtThreadSynchronized(self._registry.clear, timeout=2)
                if changed:
                    self.signals.registry_changed.emit()
                self._signals.server_disconnected.emit()
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
            elif isinstance(event, ScrutinyClient.Events.DataloggingListChanged):
                self._signals.datalogging_storage_updated.emit(event.change_type, event.acquisition_reference_id)
            else:
                self._logger.error(f"Unsupported event type : {event.__class__.__name__}")    

    def _thread_handle_download_watchable_logic(self) -> None:
        # Called from internal thread 
        if self._thread_state.runtime_watchables_download_request is not None:
            if self._thread_state.runtime_watchables_download_request.completed:  
                # Download is finished
                # Data is already inside the registry. Added from the callback
                self._logger.debug("Download of watchable list is complete. Group : runtime")
                if self._thread_state.runtime_watchables_download_request.is_success:
                    data = self._thread_state.runtime_watchables_download_request.get()
                    InvokeInQtThreadSynchronized(lambda: self._registry.write_content(data), timeout=2)
                    self._signals.registry_changed.emit()
                else:
                    InvokeInQtThreadSynchronized(lambda:self._registry.clear_content_by_type([sdk.WatchableType.RuntimePublishedValue]), timeout=2)
                self._thread_state.runtime_watchables_download_request = None   # Clear the request.
            else:
                pass # Downloading
    

        if self._thread_state.sfd_watchables_download_request is not None: 
            if self._thread_state.sfd_watchables_download_request.completed:
                # Download complete
                # Data is already inside the registry. Added from the callback
                self._logger.debug("Download of watchable list is complete. Group : SFD")
                if self._thread_state.sfd_watchables_download_request.is_success:
                    data = self._thread_state.sfd_watchables_download_request.get()
                    InvokeInQtThreadSynchronized(lambda: self._registry.write_content(data), timeout=2)
                    self._signals.registry_changed.emit()
                else:
                    InvokeInQtThreadSynchronized(lambda:self._registry.clear_content_by_type([sdk.WatchableType.Alias, sdk.WatchableType.Variable]), timeout=2)
                self._thread_state.sfd_watchables_download_request = None   # Clear the request.
            else:
                pass    # Downloading
    
    def _thread_event_device_ready(self) -> None:
        """To be called once when a device connects"""
        self._logger.debug("Detected device ready")
        req = self._thread_state.runtime_watchables_download_request    # Get the ref atomically
        if req is not None:
            req.cancel()

        self._thread_state.runtime_watchables_download_request = self._client.download_watchable_list([sdk.WatchableType.RuntimePublishedValue])
        self._signals.device_ready.emit()

    def _thread_event_sfd_loaded(self) -> None:
        """To be called once when a SFD is laoded"""
        self._logger.debug("Detected SFD loaded")
        req = self._thread_state.sfd_watchables_download_request    # Get the ref atomically
        if req is not None:
            req.cancel()
        self._thread_state.sfd_watchables_download_request = self._client.download_watchable_list([sdk.WatchableType.Variable,sdk.WatchableType.Alias])
        self.signals.sfd_loaded.emit()

    def _thread_event_sfd_unloaded(self) -> None:
        """To be called once when a SFD is unloaded"""
        self._logger.debug("Detected SFD unloaded")
        req = self._thread_state.sfd_watchables_download_request    # Get the ref atomically
        if req is not None and not req.completed:
            req.cancel()
        self._thread_state.sfd_watchables_download_request = None
        self._thread_clear_registry_synchronized([sdk.WatchableType.Alias, sdk.WatchableType.Variable])
        self.signals.sfd_unloaded.emit()

    def _thread_event_device_disconnected(self) -> None:
        """To be called once when a device disconnect"""
        self._logger.debug("Detected device disconnected")
        req = self._thread_state.runtime_watchables_download_request    # Get the ref atomically
        if req is not None and not req.completed:
            req.cancel()
        self._thread_state.runtime_watchables_download_request = None
        self._thread_clear_registry_synchronized([sdk.WatchableType.RuntimePublishedValue])
        self.signals.device_disconnected.emit()

    def _thread_clear_registry_synchronized(self, type_list:List[sdk.WatchableType]) -> None:
        @dataclass
        class Context:
            had_data:bool=False
            
        ctx = Context()
        def clear_func() -> None:
            for wt in type_list:
                had_data = self._registry.clear_content_by_type(wt)
                ctx.had_data = ctx.had_data or had_data
        if self._logger.isEnabledFor(logging.DEBUG):    # pragma: no cover
            self._logger.debug("Clearing registry for types: %s" % ([x.name for x in type_list]))
        InvokeInQtThreadSynchronized(clear_func, timeout=2)
        if self._logger.isEnabledFor(logging.DEBUG):    # pragma: no cover
            self._logger.debug("Cleared registry for types: %s" % ([x.name for x in type_list]))
        if ctx.had_data:
            self._signals.registry_changed.emit()

    
    #endregion

    #region Private QT side methods
    def _qt_update_registration_from_watchable_handle(self, 
                                                     registration_status:WatchableRegistrationStatus, 
                                                     handle:Optional[WatchableHandle]) -> None:
        """Internal function that update the registration status based on the real state of the SDK client watch handle."""
        # Update state based on SDK client
        if handle is not None:
            if handle.is_dead:
                registration_status.active_state = self.WatchableRegistrationState.UNSUBSCRIBED
            else:
                registration_status.active_state = self.WatchableRegistrationState.SUBSCRIBED
        else:
            registration_status.active_state = self.WatchableRegistrationState.UNSUBSCRIBED

    def _qt_watch_unwatch_ui_callback(self,
                            attempted_action:WatchableRegistrationAction,
                            watchable_type:sdk.WatchableType,
                            server_path:str, 
                            registration_status:WatchableRegistrationStatus,
                            error:Optional[Exception]) -> None:
        if error is not None:
            if attempted_action == self.WatchableRegistrationAction.SUBSCRIBE:
                tools.log_exception(self._logger, error, f"Failed to watch {server_path}")
            elif attempted_action == self.WatchableRegistrationAction.UNSUBSCRIBE:
                tools.log_exception(self._logger, error, f"Failed to unwatch {server_path}")
            else:
                raise NotImplementedError("Unsupported attempted action")
        
        # Update state based on SDK client
        client_handle = self._client.try_get_existing_watch_handle(server_path)
        self._qt_update_registration_from_watchable_handle(registration_status, client_handle)
        
        # Inform the listener
        if (attempted_action == self.WatchableRegistrationAction.SUBSCRIBE 
            and registration_status.active_state == self.WatchableRegistrationState.SUBSCRIBED):
            assert client_handle is not None
            self._listener.subscribe(client_handle)
        self._listener.prune_subscriptions()    # Delete dead handles
        
        if (registration_status.active_state == self.WatchableRegistrationState.UNSUBSCRIBED 
            and registration_status.pending_action==self.WatchableRegistrationAction.NONE):
            if server_path in self._registration_status_store[watchable_type]:
                del self._registration_status_store[watchable_type][server_path]    # Save some memory.
        else:
            if registration_status.pending_action == self.WatchableRegistrationAction.SUBSCRIBE:
                self._qt_maybe_request_watch(watchable_type, server_path)
            elif registration_status.pending_action == self.WatchableRegistrationAction.UNSUBSCRIBE:
                self._qt_maybe_request_unwatch(watchable_type, server_path)

        if self._unit_test:
            self._qt_watch_unwatch_ui_callback_call_count+=1

    @enforce_thread(QT_THREAD_NAME)
    def _qt_maybe_request_watch(self, watchable_type:sdk.WatchableType, server_path:str) -> None:
        """Will request the server for a watch subscription if not already done or working on it."""
        if not server_path in self._registration_status_store[watchable_type]:
            self._registration_status_store[watchable_type][server_path] = self.WatchableRegistrationStatus(
                active_state=self.WatchableRegistrationState.UNSUBSCRIBED,
                pending_action=self.WatchableRegistrationAction.NONE
            )
        registration_status = self._registration_status_store[watchable_type][server_path]

        # Update state based on SDK client
        if not registration_status.active_state.is_transition_state(): 
            client_handle = self._client.try_get_existing_watch_handle(server_path)
            self._qt_update_registration_from_watchable_handle(registration_status, client_handle)

        # Decide what to do based on active state and pending action
        if registration_status.active_state in [self.WatchableRegistrationState.SUBSCRIBED, self.WatchableRegistrationState.SUBSCRIBING]:
            # Nothing to do. Ensure we do nothing
            registration_status.pending_action = self.WatchableRegistrationAction.NONE
        elif registration_status.active_state == self.WatchableRegistrationState.UNSUBSCRIBING:
            # enqueue. Next callback will pick this up
            registration_status.pending_action = self.WatchableRegistrationAction.SUBSCRIBE
        elif registration_status.active_state == self.WatchableRegistrationState.UNSUBSCRIBED:
            # Proceed with subscription
            registration_status.pending_action = self.WatchableRegistrationAction.NONE
            registration_status.active_state = self.WatchableRegistrationState.SUBSCRIBING
            def func(client:ScrutinyClient) -> Optional[Exception]:
                try:
                    client.watch(server_path)
                except sdk.exceptions.ScrutinySDKException as e:
                    return e   # Exception others than SDKException are not normal.
                return None
    

            def ui_callback(expected_error:Optional[Exception], unexpected_error:Optional[Exception]) -> None:
                if unexpected_error is not None:
                    tools.log_exception(self._logger, unexpected_error, str_level=logging.CRITICAL)    # Not supposed to happen
                else:
                    self._qt_watch_unwatch_ui_callback(
                        attempted_action=self.WatchableRegistrationAction.SUBSCRIBE,
                        watchable_type=watchable_type, 
                        server_path=server_path, 
                        registration_status=registration_status, 
                        error=expected_error)

            self.schedule_client_request(func, ui_callback)
        else:   # pragma: no cover
            raise NotImplementedError(f"Unsupported state: {registration_status.active_state}")

    @enforce_thread(QT_THREAD_NAME)
    def _qt_maybe_request_unwatch(self, watchable_type:sdk.WatchableType, server_path:str) -> None:
        """Will request the server to unsubscribe to a watchif not already done or working on it."""
        if not server_path in self._registration_status_store[watchable_type]:
            self._registration_status_store[watchable_type][server_path] = self.WatchableRegistrationStatus(
                active_state=self.WatchableRegistrationState.UNSUBSCRIBED,
                pending_action=self.WatchableRegistrationAction.NONE
            )
        registration_status = self._registration_status_store[watchable_type][server_path]

        # Update state based on SDK client
        if not registration_status.active_state.is_transition_state(): # Handle is subscribed or unsubscribed. no intermediate state
            client_handle = self._client.try_get_existing_watch_handle(server_path)
            self._qt_update_registration_from_watchable_handle(registration_status, client_handle)
        
        if registration_status.active_state in [self.WatchableRegistrationState.UNSUBSCRIBED, self.WatchableRegistrationState.UNSUBSCRIBING]:
            # Nothing to do. Ensure we do nothing
            registration_status.pending_action = self.WatchableRegistrationAction.NONE
        elif registration_status.active_state == self.WatchableRegistrationState.SUBSCRIBING:
            # enqueue. Next callback will pick this up
            registration_status.pending_action = self.WatchableRegistrationAction.UNSUBSCRIBE
        elif registration_status.active_state == self.WatchableRegistrationState.SUBSCRIBED:
            # Proceed with unsubscription
            registration_status.pending_action = self.WatchableRegistrationAction.NONE
            registration_status.active_state = self.WatchableRegistrationState.UNSUBSCRIBING
            def func(client:ScrutinyClient) -> Optional[Exception]:
                try:
                    client.unwatch(server_path)
                except sdk.exceptions.ScrutinySDKException as e:
                    return e   # Exception others than SDKException are not normal.
                return None

            def ui_callback(expected_error:Optional[Exception], unexpected_error:Optional[Exception]) -> None:
                if unexpected_error is not None:
                    tools.log_exception(self._logger, unexpected_error, str_level=logging.CRITICAL)    # Not supposed to happen
                else:
                    self._qt_watch_unwatch_ui_callback(
                        attempted_action=self.WatchableRegistrationAction.UNSUBSCRIBE,
                        watchable_type=watchable_type, 
                        server_path=server_path, 
                        registration_status=registration_status, 
                        error=expected_error)

            self.schedule_client_request(func,ui_callback)
        else:   # pragma: no cover
            raise NotImplementedError(f"Unsupported state: {registration_status.active_state}")

    @enforce_thread(QT_THREAD_NAME)
    def _qt_registry_watch_callback(self, watcher_id:Union[str,int], server_path:str, watchable_config:sdk.WatchableConfiguration) -> None:
        """Called when a gui component register a watcher on the registry"""
        # Runs from QT thread
        watcher_count = self._registry.node_watcher_count(watchable_config.watchable_type, server_path)
        if watcher_count is not None and watcher_count > 0:
            self._qt_maybe_request_watch(watchable_config.watchable_type, server_path)

    @enforce_thread(QT_THREAD_NAME)
    def _qt_registry_unwatch_callback(self, watcher_id:Union[str,int], server_path:str, watchable_config:sdk.WatchableConfiguration) -> None:
        """Called when a gui component unregister a watcher on the registry"""
        # Runs from QT thread
        watcher_count = self._registry.node_watcher_count(watchable_config.watchable_type, server_path)
        if watcher_count is not None and watcher_count == 0:
            self._qt_maybe_request_unwatch(watchable_config.watchable_type, server_path)

    def _qt_value_update_received(self) -> None:
        # Called in the QT thread when a value update is received by the lsitener (the client)
        aggregated_updates:List[ValueUpdate] = []
        while not self._listener.to_gui_thread_queue.empty():
            update_list = self._listener.to_gui_thread_queue.get_nowait()
            aggregated_updates.extend(update_list)

        self._registry.broadcast_value_updates_to_watchers(aggregated_updates)
        self._listener.ready_for_next_update()
    
    def _qt_client_request_completed(self, store_id:int) -> None:
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

    @enforce_thread(QT_THREAD_NAME)
    def _qt_thread_join_thread_and_emit_stopped(self) -> None:
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

    @enforce_thread(QT_THREAD_NAME)
    def _set_loaded_sfd(self, sfd:Optional[sdk.SFDInfo]) -> None:
        need_event = (sfd != self._loaded_sfd)
        self._loaded_sfd = sfd
        if need_event:
            InvokeQueued(lambda: self._signals.loaded_sfd_availability_changed.emit())

    @enforce_thread(QT_THREAD_NAME)
    def _set_device_info(self, device_info:Optional[sdk.DeviceInfo]) -> None:
        need_event = (device_info != self._device_info)
        self._device_info = device_info
        if need_event:
            InvokeQueued(lambda: self._signals.device_info_availability_changed.emit())

    @enforce_thread(QT_THREAD_NAME)
    def _sfd_loaded_callback(self) -> None:
        # Called in the UI thread when we emit the signal : sfd_laoded.
        # Use to download the SFD data
        info = self.get_server_info()
        if info is not None:
            if info.sfd_firmware_id is not None:
                sfd_firmware_id = info.sfd_firmware_id
                def func(client:ScrutinyClient) -> Tuple[str, Optional[sdk.SFDInfo]]:
                    loaded_sfd = client.get_loaded_sfd()
                    return sfd_firmware_id, loaded_sfd

                self.schedule_client_request(func, self._receive_loaded_sfd_info)
    
    @enforce_thread(QT_THREAD_NAME)
    def _sfd_unloaded_callback(self) -> None:
        # Called when the server manager emit the signal : sfd_unloaded
        self._set_loaded_sfd(None)
    

    @enforce_thread(QT_THREAD_NAME)
    def _device_ready_callback(self) -> None:
        # Called when the server manager emit the signal : device_connected
        info = self.get_server_info()
        if info is not None:
            if info.device_session_id is not None:
                session_id = info.device_session_id
                def func(client:ScrutinyClient) -> Tuple[str, Optional[sdk.DeviceInfo]]:
                    device_info = client.get_device_info()
                    return session_id, device_info
            
                self.schedule_client_request(func, self._receive_device_info)

    @enforce_thread(QT_THREAD_NAME)
    def _device_disconnected_callback(self) -> None:
        # Called when the server manager emit the signal : device_disconnected
        self._set_device_info(None)

    @enforce_thread(QT_THREAD_NAME)
    def _receive_device_info(self, retval:Optional[Any], error:Optional[Exception]) -> None:
        # Called when client.get_device_info() completes
        valid = False
        device_info:Optional[sdk.DeviceInfo] = None
        if retval is not None:
            server_info = self.get_server_info()
            if server_info is not None:
                if server_info.device_session_id is not None:
                    session_id, device_info = cast(Tuple[str, sdk.DeviceInfo], retval)
                    if server_info.device_session_id == session_id: # Is unchanged since request is initiated
                        valid = True
        else:
            if error is not None:
                self._logger.error(f"Failed to download the device information: {error}")

        if valid:
            assert device_info is not None
            self._set_device_info(device_info)
            self._device_info = device_info
        else:
            self._set_device_info(None)
        
        self._signals.device_info_availability_changed

    @enforce_thread(QT_THREAD_NAME)
    def _receive_loaded_sfd_info(self, retval:Optional[Any], error:Optional[Exception]) -> None:
        # Called when client.get_loaded_sfd() completes.
        valid = False
        loaded_sfd:Optional[sdk.SFDInfo] = None
        if retval is not None:  # Success
            server_info = self.get_server_info()
            if server_info is not None:
                if server_info.sfd_firmware_id is not None:
                    sfd_firmware_id, loaded_sfd = cast(Tuple[str, sdk.SFDInfo], retval)
                    if server_info.sfd_firmware_id == sfd_firmware_id:  # Is unchanged since request is initiated
                        valid = True
        else:
            if error is not None:
                self._logger.error(f"Failed to download the SFD details: {error}")
                tools.log_exception(self._logger, error)

        if valid:
            assert loaded_sfd is not None
            self._set_loaded_sfd(loaded_sfd)
        else:
            self._set_loaded_sfd(None)

    def _server_disconnected_callback(self) -> None:
        self._set_device_info(None)
        self._set_loaded_sfd(None)
        
    #endregion


    #region Public - Fully thread safe

    def schedule_client_request(self, 
            user_func:Callable[[ScrutinyClient], Any], 
            ui_thread_callback:Callable[[Any, Optional[Exception]], None]
            ) -> None:
        """Runs a client request in a separate thread and calls a callback in the UI thread when done."""
        # Thread safe. Can be called from any thread

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

    def get_server_state(self) -> sdk.ServerState:
        # Called from QT thread + Server thread. atomic
        return self._client.server_state
    
    def get_server_info(self) -> Optional[sdk.ServerInfo]:
        # Called from QT thread + Server thread. atomic
        try:
            return self._client.get_latest_server_status()
        except sdk.exceptions.ScrutinySDKException:
            return None
    
    def get_device_info(self) -> Optional[sdk.DeviceInfo] :
        return copy(self._device_info)

    def get_loaded_sfd(self) -> Optional[sdk.SFDInfo] :
        return copy(self._loaded_sfd)


    @property
    def signals(self) -> _Signals:
        """The events exposed to the application"""
        return self._signals
    #endregion

    #region Public -  QT side methods

    @enforce_thread(QT_THREAD_NAME)
    def qt_write_watchable_value(self, fqn:str, value:Union[str, int, float, bool], callback:Callable[[Optional[Exception]], None]) -> None:
        """Request the server manager to write the value of a node in the registry idetified by its Fully Qualified Name.
        Must be called from QT thread
        
        :param fqn: The Fully Qulified Name of the watchable
        :param callback: A callback to call on completion. If the single parameter is None, completed successfully, otherwise will be the exception raised

        """
        watchable_config = self._registry.get_watchable_fqn(fqn)
        if watchable_config is None:
            raise Exception(f"Item {fqn} is not in the registry. Cannot write its value")
        def threaded_func(client:ScrutinyClient) -> None:
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

    @enforce_thread(QT_THREAD_NAME)
    def exit(self)->None:
        self.stop()
        self._exit_in_progress = True
    
    @enforce_thread(QT_THREAD_NAME)
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
        self._set_device_info(None)
        self._set_loaded_sfd(None)
        self._client_request_store.clear()
        self.signals.starting.emit()
        self._allow_auto_reconnect = True
        self._thread_stop_event.clear()
        self._thread = threading.Thread(target=self._thread_func, args=[config], daemon=True)
        self._listener.reset_stats()
        self._thread.start()
        self._logger.debug("Server manager started")
        self.signals.started.emit()
    
    @enforce_thread(QT_THREAD_NAME)
    def stop(self) -> None:
        """Stops the server manager. Will disconnect it from the server and clear all internal data"""
        # Called from the QT thread
        self._logger.debug("ServerManager.stop() called")
        if self._stop_pending:
            self._logger.debug("Stop already pending. Cannot stop")
            return
        
        if not self.is_running():
            self._logger.debug("Server manager is not running. Cannot stop")
            return 
        
        self._logger.debug("Stopping server manager")
        UserMessagesManager.instance().clear_message(USER_MSG_ID_CONNECT_FAILED)
        self._stop_pending = True
        self._set_device_info(None)
        self._set_loaded_sfd(None)
        self.signals.stopping.emit()

        # Will cause the thread to exit and emit thread_exit_signal that triggers _qt_thread_join_thread_and_emit_stopped in the UI thread
        self._thread_stop_event.set()
        self._client.close_socket()   # Will cancel any pending request in the other thread
        self._logger.debug("Stop initiated")

    def is_running(self) -> bool:
        """Returns ``True`` if the server manager is started and fully working."""
        return self._thread is not None and self._thread.is_alive() and not self._stop_pending

    def is_stopping(self) -> bool:
        """Returns ``True`` if ``stop()`` has been called but the internal thread has not yet exited."""
        return self._stop_pending

    #endregion
   
