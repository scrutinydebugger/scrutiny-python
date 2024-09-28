__all__ = ['ServerManager']

from scrutiny import sdk
from scrutiny.sdk.client import ScrutinyClient
from scrutiny.gui.exceptions import GuiError
from enum import Enum
import threading
import time
from dataclasses import dataclass

from qtpy.QtCore import QTimer, QTimerEvent, Signal, QObject
import logging
from typing import Optional
import traceback

class ServerManagerError(GuiError):
    pass

@dataclass(init=False)
class ThreadData:
    thread:Optional[threading.Thread]
    started_event:threading.Event

    def __init__(self) -> None:
        self.thread = None
        self.started_event = threading.Event()



class ServerManager:

    class ThreadFSMData:
        previous_server_stat:sdk.ServerState
        server_state:sdk.ServerState
        server_info:Optional[sdk.ServerInfo]
        previous_server_info:Optional[sdk.ServerInfo]

        def __init__(self) -> None:
            self.clear()

        def clear(self) -> None:
            self.previous_server_state = sdk.ServerState.Disconnected
            self.server_state = sdk.ServerState.Disconnected
            self.server_info = None
            self.previous_server_info = None


    class _Signals(QObject):
        server_connected = Signal()
        server_disconnected = Signal()
        device_ready = Signal()
        device_disconnected = Signal()
        datalogging_state_changed = Signal()


    _client:ScrutinyClient
    _thread:Optional[threading.Thread]
    _thread_stop_event:threading.Event
    _signals:_Signals
    _auto_reconnect:bool
    _logger:logging.Logger
    _fsm_data:ThreadFSMData

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

    @property
    def signals(self) -> _Signals:
        return self._signals

    
    def start(self, hostname:str, port:int) -> None:
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
        self._fsm_data.clear()


    def _thread_func(self, hostname:str, port:int) -> None:
        
        self._fsm_data.previous_server_state = sdk.ServerState.Disconnected
        self._fsm_data.server_state = sdk.ServerState.Disconnected
        self._fsm_data.server_info = None
        self._fsm_data.previous_server_info = None
        
        while not self._thread_stop_event.is_set():

            self._fsm_data.server_state = self._client.server_state
            state_entry = self._fsm_data.server_state != self._fsm_data.previous_server_state
            
            if self._fsm_data.server_state == sdk.ServerState.Disconnected:
                if state_entry:
                    self._signals.server_disconnected.emit()
                
                self._fsm_data.server_info = None
                self._fsm_data.previous_server_info = None

                if self._auto_reconnect:
                    try:
                        self._logger.debug("Connecting client")
                        self._client.connect(hostname, port, wait_status=False)
                    except sdk.exceptions.ConnectionError:
                        pass
            
            elif self._fsm_data.server_state == sdk.ServerState.Connecting:
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
                    if self._fsm_data.previous_server_info.device_session_id is not None:
                        self._signals.device_disconnected.emit()
                
                # Server just arrived
                elif self._fsm_data.server_info is not None and self._fsm_data.previous_server_info is None:
                    if self._fsm_data.server_info.device_session_id is not None:
                        self._signals.device_ready.emit()

                
                # Server is running
                elif self._fsm_data.server_info is not None and self._fsm_data.previous_server_info is not None:
                    if (
                        self._fsm_data.server_info.device_session_id is not None    # No need to trigger that event when the device is gone
                        and self._fsm_data.previous_server_info.device_session_id is not None    # No need to trigger that event when the device is gone
                        and (
                            # Trigger on state change or completion ration change.
                            self._fsm_data.server_info.datalogging.state != self._fsm_data.previous_server_info.datalogging.state 
                            or self._fsm_data.server_info.datalogging.completion_ratio != self._fsm_data.previous_server_info.datalogging.completion_ratio
                        )
                    ):
                        self._signals.datalogging_state_changed.emit()
                    
                    if self._fsm_data.server_info.device_session_id is None and self._fsm_data.previous_server_info.device_session_id is not None:
                        self._signals.device_disconnected.emit()
                    elif self._fsm_data.server_info.device_session_id is not None and self._fsm_data.previous_server_info.device_session_id is None:
                        self._signals.device_ready.emit()
                    elif self._fsm_data.server_info.device_session_id is not None and self._fsm_data.previous_server_info.device_session_id is not None:
                        if self._fsm_data.server_info.device_session_id != self._fsm_data.previous_server_info.device_session_id:
                            # The server did a full reconnect between 2 state update.
                            # This state hsa a value only when device state is ConnectedReady
                            self._signals.device_disconnected.emit()
                            self._signals.device_ready.emit()
                    else: # Both None, nothing to do
                        pass
                else:
                    pass # Nothing to do

                self._fsm_data.previous_server_info=self._fsm_data.server_info

            elif self._fsm_data.server_state == sdk.ServerState.Error:
                self._logger.critical("Server state is Error. Stopping the server manager")
                self._auto_reconnect = False
                self._client.disconnect()
                self._thread_stop_event.set()

            self._fsm_data.previous_server_state = self._fsm_data.server_state

    
    def get_server_state(self) -> sdk.ServerState:
        return self._client.server_state
    
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
