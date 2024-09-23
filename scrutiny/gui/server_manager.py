from scrutiny import sdk
from scrutiny.sdk.client import ScrutinyClient
from scrutiny.gui.exceptions import GuiError
from enum import Enum
import threading
import time

from qtpy.QtCore import QTimer, QTimerEvent
import logging
from typing import Optional
import traceback

class ServerManagerError(GuiError):
    pass

class ServerManager:
    _hostname:str
    _port:int
    _started:bool
    
    _connect_thread:Optional[threading.Thread]
    _connect_thread_started:threading.Event
    _request_connect_thread_exit:bool
    _wake_event:threading.Event
    _request_disconnect_event:threading.Event

    _client:ScrutinyClient
    _logger = logging.Logger
    
    RETRY_INTERVAL_SEC = 2 # seconds

    def __init__(self) -> None:
        self._hostname = ""
        self._port = -1
        self._started = False
        
        self._connect_thread = None
        self._connect_thread_started = threading.Event()
        self._wake_event = threading.Event()
        self._request_disconnect_event = threading.Event()
        self._request_connect_thread_exit = False
        
        self._client = ScrutinyClient()
        self._logger = logging.getLogger(self.__class__.__name__)

    def start(self, hostname:str, port:int) -> None:
        if self._started:
            raise ServerManagerError(f"Server manager already running")
        
        self._logger.debug("Starting Server Manager")
        self._hostname = hostname
        self._port = port

        self._connect_thread = threading.Thread(self.connect_thread)
        self._connect_thread_started.clear()
        self._wake_event.clear()
        self._request_disconnect_event.clear()

        self._request_connect_thread_exit = False
        self._connect_thread.start()
        self._connect_thread_started.wait()
        self._logger.debug("Server Manager started")
    
    def stop(self, join:bool=False) -> None:
        if not self._started:
            raise ServerManagerError(f"Server manager already stopped")
        
        self._logger.debug("Stopping Server Manager")
        self._request_disconnect_event.set()
        self._request_connect_thread_exit = True
        self._wake_event.set()
        self._started = False
    
    def is_stopped(self):
        return not self._started  and not self._connect_thread.is_alive()

    def _connect_thread(self):
        self._connect_thread_started.set()
        last_trial = time.monotonic()
        
        while not self._request_connect_thread_exit:
            self._wake_event.wait(0.1)
            self._wake_event.clear()

            try:
                if self._request_disconnect_event.is_set():
                    try:
                        self._logger.debug(f"Disconnecting")
                        self._client.disconnect()
                    except sdk.exceptions.ConnectionError as e:
                        self._logger.error(f"Error While disconnecting {e}")
                        self._logger.debug(traceback.format_exc())
                    self._request_disconnect_event.clear()
                else:
                    if self._started:
                        if self._client.server_state == sdk.ServerState.Disconnected:
                            if time.monotonic() - last_trial > self.RETRY_INTERVAL_SEC:
                                try:
                                    self._logger.debug(f"Trying to connect {self._hostname}:{self._port}")
                                    self._client.connect(self._hostname, self._port)
                                except sdk.exceptions.ConnectionError:
                                    self._logger.debug("Failed to connect")
                                finally:
                                    last_trial = time.monotonic()
            except Exception as e:
                self._logger.error(f"Unexpected error {e}")
                self._logger.debug(traceback.format_exc())
                try:
                    self._client.disconnect()
                except Exception:
                    pass
                self._request_connect_thread_exit = True
            

    def get_server_state(self) -> sdk.ServerState:
        return self._client.server_state
