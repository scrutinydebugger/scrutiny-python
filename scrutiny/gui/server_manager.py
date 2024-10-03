__all__ = ['ServerManager']

from scrutiny import sdk
from scrutiny.sdk.client import ScrutinyClient, WatchableListDownloadRequest
from dataclasses import dataclass
import threading
import time
import traceback

from qtpy.QtCore import Signal, QObject
from typing import Optional, Dict, List
import logging

from scrutiny.gui.watchable_storage import WatchableStorage

@dataclass(init=False)
class ThreadData:
    thread:Optional[threading.Thread]
    started_event:threading.Event

    def __init__(self) -> None:
        self.thread = None
        self.started_event = threading.Event()


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
        
        def clear_download_requests(self):
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


    class _Signals(QObject):    # QObject required for signals to work
        """Signals offered to the outside worl"""
        server_connected = Signal()
        server_disconnected = Signal()
        device_ready = Signal()
        device_disconnected = Signal()
        datalogging_state_changed = Signal()
        sfd_loaded = Signal()
        sfd_unloaded = Signal()


    RECONNECT_DELAY = 1
    _client:ScrutinyClient              # The SDK client object that talks with the server
    _thread:Optional[threading.Thread]  # The thread tyhat runs the synchronous client
    _storage:WatchableStorage

    _thread_stop_event:threading.Event  # Event used to stop the thread
    _signals:_Signals                   # The signals
    _auto_reconnect:bool                # Flag indicating if the thread should try to reconnect the client if disconnected
    _logger:logging.Logger              # Logger
    _fsm_data:ThreadFSMData             # Data used by the thread to detect state changes

    def __init__(self, client:Optional[ScrutinyClient]=None) -> None:
        super().__init__()  # Required for signals to work
        if client is None:
            self._client = ScrutinyClient()
        else:
            self._client = client   # Mainly useful for unit testing
        self._signals = self._Signals()
        
        self._thread = None
        self._thread_stop_event = threading.Event()
        self._auto_reconnect = False
        self._logger = logging.getLogger(self.__class__.__name__)
        self._fsm_data = self.ThreadFSMData()
        self._storage = WatchableStorage()

    @property
    def signals(self) -> _Signals:
        """The events exposed to the application"""
        return self._signals

    @property
    def storage(self) -> WatchableStorage:
        """The watchable storage"""
        return self._storage

    
    def start(self, hostname:str, port:int) -> None:
        """Makes the server manager try to connect and monitor server state changes
        Will autoreconnect on disconnection
        """
        self._logger.debug("ServerManager.start() called")
        if self.is_running():
            self.stop()

        self._logger.debug("Starting server manager")
        self._auto_reconnect = True
        self._thread_stop_event.clear()
        self._thread = threading.Thread(target=self._thread_func, args=[hostname, port], daemon=True)
        self._thread.start()
        self._logger.debug("Server manager started")
    
    def stop(self) -> None:
        """Stops the server manager. Will disconnect it from the server and clear all internal data"""
        self._logger.debug("ServerManager.stop() called")
        self._auto_reconnect = False
        self._client.disconnect()

        # Ensure the server thread has the time to notice the changes and emit all signals
        t = time.monotonic()
        timeout = 1
        while self._fsm_data.server_state != sdk.ServerState.Disconnected and time.monotonic() - t < timeout:
            time.sleep(0.01)

        if self._thread is not None:
            if self._thread.is_alive():
                self._logger.debug("Stopping server manager")
                self._thread_stop_event.set()
                self._thread.join(2)
                if self._thread.is_alive():
                    self._logger.error("Failed to stop the internal thread")
                else:
                    self._logger.debug("Server manager stopped")
        
        self._thread = None


    def _thread_func(self, hostname:str, port:int) -> None:
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
                
                if self._fsm_data.server_state == sdk.ServerState.Disconnected:
                    if state_entry: # Will not enter on first loop. On purpose.
                        self._logger.debug("Entering disconnected state")
                        self._signals.server_disconnected.emit()
                    
                    self._fsm_data.server_info = None
                    self._fsm_data.previous_server_info = None
                    self._fsm_data.clear_download_requests()
                    self._storage.clear()   # Emit signals only on change

                    if self._auto_reconnect:
                        # timer to prevent going crazy on function call
                        if self._fsm_data.connect_timestamp_mono is None or time.monotonic() - self._fsm_data.connect_timestamp_mono > self.RECONNECT_DELAY:
                            try:
                                self._logger.debug("Connecting client")
                                self._fsm_data.connect_timestamp_mono = time.monotonic()
                                self._client.connect(hostname, port, wait_status=False)
                            except sdk.exceptions.ConnectionError:
                                pass
                
                elif self._fsm_data.server_state == sdk.ServerState.Connecting: # pragma: no cover
                    pass    # This state should never happen here because connect block until completion or failure

                elif self._fsm_data.server_state == sdk.ServerState.Connected:
                    if state_entry:
                        self._logger.debug(f"Client connected to {hostname}:{port}")
                        self._signals.server_connected.emit()
                        self._fsm_data.server_info = None
                        self._fsm_data.previous_server_info = None

                    try:
                        self._client.wait_server_status_update(0.2)
                        self._fsm_data.server_info = self._client.get_server_status()
                    except sdk.exceptions.TimeoutException:
                        pass
                    except sdk.exceptions.ScrutinySDKException:
                        self._fsm_data.server_info = None

                    # Server is gone
                    if self._fsm_data.server_info is None and self._fsm_data.previous_server_info is not None:
                        if self._fsm_data.previous_server_info.sfd is not None:
                            self._thread_sfd_unloaded()
                        if self._fsm_data.previous_server_info.device_session_id is not None:
                            self._thread_device_disconnected()
                    
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
                    self._client.disconnect()
                    self._fsm_data.clear_download_requests()
                    self._thread_stop_event.set()

                self._fsm_data.previous_server_state = self._fsm_data.server_state

            
        except Exception as e:
            self._logger.error(f"Error in server manager thread: {e}")
            self._logger.debug(traceback.format_exc())

        
        self._fsm_data.clear()
        self._logger.debug("Server Manager thread exiting")

    def _thread_handle_download_watchable_logic(self) -> None:
        # Handle download of RPV if the device is ready
        device_ready = self._fsm_data.server_info.device_session_id is not None
        has_rpv = self._storage.has_data(sdk.WatchableType.RuntimePublishedValue)
        
        if device_ready:
            if not has_rpv:
                if self._fsm_data.runtime_watchables_download_request is None:
                    self._logger.critical("Device is ready but no watcahble request has been initiated")     # pragma: no cover
                elif self._fsm_data.runtime_watchables_download_request.completed:  # Download is ready
                    self._logger.debug("Download of watchable list is complete. Group : runtime")
                    data = self._fsm_data.runtime_watchables_download_request.get()
                    assert data is not None
                    # Let's take ownership of the data in the request using copy=False . 
                    # The SDK is expected to leave the data untouched after request completion.
                    self._storage.set_content_by_types([sdk.WatchableType.RuntimePublishedValue], data,copy=False)
                    self._fsm_data.runtime_watchables_download_request = None   # Release the reference to the data
                else:
                    pass # Downloading
        else:
            if has_rpv: # pragma: no cover
                self._logger.critical("The device is not available but there is still data in the watchable storage.")
                self.storage.clear()

    
        # Handle the download of variables and alias if the SFD is loaded
        sfd_loaded = self._fsm_data.server_info.sfd is not None
        has_alias_var = self._storage.has_data(sdk.WatchableType.Alias) and self._storage.has_data(sdk.WatchableType.Variable)
        if sfd_loaded:
            if not has_alias_var:
                if self._fsm_data.sfd_watchables_download_request is None:  # pragma: no cover
                   self._logger.critical("Device is ready but no watcahble request has been initiated")  

                elif self._fsm_data.sfd_watchables_download_request.completed:
                    # Download complete
                    self._logger.debug("Download of watchable list is complete. Group : SFD")
                    data = self._fsm_data.sfd_watchables_download_request.get()
                    assert data is not None
                    # Let's take ownership of the data in the request using copy=False . 
                    # The SDK is expected to leave the data untouched after request completion.
                    self._storage.set_content_by_types([sdk.WatchableType.Alias, sdk.WatchableType.Variable], data, copy=False)
                    self._fsm_data.sfd_watchables_download_request = None   # Release the reference to the data
                else:
                    pass    # Downloading

        else:   # No SFD loaded
            if has_alias_var:   # pragma: no cover
                self._logger.critical("The SFD is not loaded but there is still data in the watchable storage.")
                self.storage.clear()

 
    def _thread_device_ready(self) -> None:
        self._logger.debug("Detected device ready")
        self._fsm_data.clear_download_requests()
        self._storage.clear()    
        self._fsm_data.runtime_watchables_download_request = self._client.download_watchable_list([sdk.WatchableType.RuntimePublishedValue])
        self._signals.device_ready.emit()

    def _thread_sfd_loaded(self) -> None:
        self._logger.debug("Detected SFD loaded")
        req = self._fsm_data.sfd_watchables_download_request    # Get the ref atomically
        if req is not None:
            req.cancel()
        self._fsm_data.sfd_watchables_download_request = self._client.download_watchable_list([sdk.WatchableType.Variable,sdk.WatchableType.Alias])
        self.signals.sfd_loaded.emit()
    
    def _thread_sfd_unloaded(self) -> None:
        self._logger.debug("Detected SFD unloaded")
        req = self._fsm_data.sfd_watchables_download_request    # Get the ref atomically
        if req is not None:
            req.cancel()
        self._fsm_data.sfd_watchables_download_request = None
        self._storage.clear_content_by_types([sdk.WatchableType.Alias, sdk.WatchableType.Variable])

        self.signals.sfd_unloaded.emit()

    def _thread_device_disconnected(self) -> None:
        self._logger.debug("Detected device disconnected")
        self._fsm_data.clear_download_requests()
        self._storage.clear()
        self._signals.device_disconnected.emit()

    def get_server_state(self) -> sdk.ServerState:
        return self._client.server_state
    
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
