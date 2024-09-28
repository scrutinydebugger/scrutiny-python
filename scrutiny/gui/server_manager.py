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

    class _Signals(QObject):
        server_connected_signal = Signal()
        server_disconnected_signal = Signal()
        device_connected = Signal()
        device_ready = Signal()
        device_disconnected = Signal()
        datalogging_state_changed = Signal()


    _client:ScrutinyClient
    _thread:Optional[threading.Thread]
    _thread_stop_event:threading.Event
    _signals:_Signals
    _auto_reconnect:bool
    _logger:logging.Logger

    def __init__(self) -> None:
        super().__init__()  # Required for signals to work
        self._client = ScrutinyClient()
        self._signals = ServerManager._Signals()
        
        self._thread = None
        self._thread_stop_event = threading.Event()
        self._auto_reconnect = False
        self._logger = logging.getLogger(self.__class__.__name__)

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
        
        previous_server_state = sdk.ServerState.Disconnected
        server_state = sdk.ServerState.Disconnected
        server_info:Optional[sdk.ServerInfo] = None
        previous_server_info:Optional[sdk.ServerInfo] = None
        
        while not self._thread_stop_event.is_set():

            server_state = self._client.server_state
            state_entry = server_state != previous_server_state
            
            if server_state == sdk.ServerState.Disconnected:
                if state_entry:
                    self._signals.server_disconnected_signal.emit()
                
                server_info = None
                previous_server_info = None

                if self._auto_reconnect:
                    try:
                        self._logger.debug("(Re)connecting client")
                        self._client.connect(hostname, port, wait_status=False)
                    except sdk.exceptions.ConnectionError:
                        pass
            
            elif server_state == sdk.ServerState.Connecting:
                pass    # connect should block for this state to never happen

            elif server_state == sdk.ServerState.Connected:
                if state_entry:
                    self._logger.debug(f"Client connected to {hostname}:{port}")
                    self._signals.server_connected_signal.emit()
                    server_info = None
                    previous_server_info = None

                try:
                    self._client.wait_server_status_update(0.5)
                    server_info = self._client.get_server_status()
                except sdk.exceptions.TimeoutException:
                    pass
                except sdk.exceptions.ScrutinySDKException:
                    server_info = None

                # Server is gone
                if server_info is None and previous_server_info is not None:
                    self._signals.datalogging_state_changed.emit()

                    if previous_server_info.device_session_id is not None:
                        self._signals.device_disconnected.emit()
                
                # Server just arrived
                elif server_info is not None and previous_server_info is None:
                    self._signals.datalogging_state_changed.emit()

                    if server_info.device_session_id is not None:
                        self._signals.device_connected.emit()
                
                # Server is running
                elif server_info is not None and previous_server_info is not None:
                    if (
                        server_info.datalogging.state != previous_server_info.datalogging.state 
                        or server_info.datalogging.completion_ratio != previous_server_info.datalogging.completion_ratio
                        ):
                        self._signals.datalogging_state_changed.emit()
                    
                    if server_info.device_session_id != previous_server_info.device_session_id:
                        # The server did a full reconnect between 2 state update.
                        # This state hsa a value only when device state is ConnectedReady
                        self._signals.device_disconnected.emit()
                        self._signals.device_connected.emit()
                else:
                    pass # Nothing to do

                previous_server_info=server_info

            elif server_state == sdk.ServerState.Error:
                self._logger.critical("Server state is Error. Stopping the server manager")
                self._auto_reconnect = False
                self._client.disconnect()
                self._thread_stop_event.set()

            previous_server_state = server_state

    
    def get_server_state(self) -> sdk.ServerState:
        return self._client.server_state
    
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
