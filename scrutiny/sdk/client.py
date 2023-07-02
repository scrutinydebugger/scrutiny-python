__all__ = ['Client']


from scrutiny.sdk.definitions import *
from scrutiny.sdk.watchable_handle import WatchableHandle
import scrutiny.sdk.exceptions as sdk_exceptions

import logging
import traceback
import threading
import socket
import websockets
import websockets.sync.client
import websockets.exceptions
import json
import time
from dataclasses import dataclass

from typing import *


class ScrutinyClient:

    RxMessageCallback = Callable[["ScrutinyClient", object], None]

    @dataclass
    class ThreadingEvents:
        stop_rx_thread: threading.Event
        disconnect: threading.Event
        disconnected: threading.Event
        msg_received: threading.Event

        def __init__(self):
            self.stop_rx_thread = threading.Event()
            self.disconnect = threading.Event()
            self.disconnected = threading.Event()
            self.msg_received = threading.Event()

    _name: Optional[str]
    _server_state: ServerState
    _hostname: Optional[str]
    _port: Optional[int]
    _logger: logging.Logger
    _encoding: str
    _conn: Optional[websockets.sync.client.ClientConnection]
    _rx_message_callbacks: List[RxMessageCallback]

    _rx_thread: Optional[threading.Thread]
    _threading_events: ThreadingEvents
    _conn_lock: threading.Lock
    _state_lock: threading.Lock

    def __init__(self,
                 name: Optional[str] = None,
                 rx_message_callbacks: Optional[List[RxMessageCallback]] = None
                 ):
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
        self._rx_thread = None
        self._threading_events = self.ThreadingEvents()
        self._conn_lock = threading.Lock()
        self._state_lock = threading.Lock()

    def _start_rx_thread(self) -> None:
        self._threading_events.stop_rx_thread.clear()
        self._threading_events.disconnect.clear()
        started_event = threading.Event()
        self._rx_thread = threading.Thread(target=self._rx_thread_task, args=[started_event])
        self._rx_thread.start()
        started_event.wait()
        self._logger.debug('RX thread started')

    def _stop_rx_thread(self) -> None:
        if self._rx_thread is not None:
            if self._rx_thread.is_alive():
                self._threading_events.stop_rx_thread.set()
                self._rx_thread.join()
            self._rx_thread = None

    def _rx_thread_task(self, started_event: threading.Event) -> None:
        started_event.set()

        while not self._threading_events.stop_rx_thread.is_set() and self._conn is not None:
            try:

                msg = self._rxt_recv(timeout=0.001)
                if msg is not None:
                    self._threading_events.msg_received.set()
                    for callback in self._rx_message_callbacks:
                        callback(self, msg)

            except sdk_exceptions.ConnectionError as e:
                self._logger.error(f"Exception in thread: {e}")
                self._rxt_disconnect()

            if self._threading_events.disconnect.is_set():
                self._rxt_disconnect()  # Will set _conn to None
                self._threading_events.disconnected.set()

            time.sleep(0.005)
        self._logger.debug('RX thread stopped')
        self._threading_events.stop_rx_thread.clear()

    def connect(self, hostname: str, port: int, **kwargs) -> None:
        """Connect to a Scrutiny server through a websocket.

        :param hostname: The hostname or ip address of the server
        :param port: The listening port of the server

        :raises ``scrutiny.sdk.exceptions.ConnectionError``: In case of failure
        """
        self.disconnect()

        self._hostname = hostname
        self._port = port
        uri = f'ws://{self._hostname}:{self._port}'
        connect_error: Optional[Exception] = None
        self._logger.info(f"Connecting to {uri}")
        try:
            self._server_state = ServerState.Connecting
            self._conn = websockets.sync.client.connect(uri, **kwargs)
            self._server_state = ServerState.Connected

            self._start_rx_thread()
        except (websockets.exceptions.WebSocketException, socket.error) as e:
            self._logger.debug(traceback.format_exc())
            connect_error = e

        if connect_error is not None:
            self.disconnect()
            raise sdk_exceptions.ConnectionError(f'Failed to connect to the server at "{uri}". Error: {connect_error}')

    def disconnect(self):
        if self._rx_thread is None:
            self._rxt_disconnect()  # Can call safely from this thread
            return

        if not self._rx_thread.is_alive():
            self._rxt_disconnect()  # Can call safely from this thread
            return

        self._threading_events.disconnected.clear()
        self._threading_events.disconnect.set()
        self._threading_events.disconnected.wait(timeout=1)  # Timeout avoid race condition if the thread was exiting

        self._stop_rx_thread()

    def _rxt_disconnect(self):
        """Disconnect from a Scrutiny server .
            Does not throw an exception in case of broken pipe
        """

        self._conn_lock.acquire()
        if self._conn is not None:
            self._logger.info(f"Disconnecting from server at {self._hostname}:{self._port}")
            try:
                self._conn.close()
            except (websockets.exceptions.WebSocketException, socket.error):
                self._logger.debug("Failed to close the websocket")
                self._logger.debug(traceback.format_exc())

        self._conn = None
        self._conn_lock.release()

        self._state_lock.acquire()
        self._hostname = None
        self._port = None
        self._server_state = ServerState.Disconnected
        self._state_lock.release()

    def _send(self, obj: dict) -> None:
        """Sends binary payload

        :raises ``scrutiny.sdk.exceptions.ConnectionError``: In case of failure
        :raises ``TypeError``: If the input is not a dictionary
        """
        error: Optional[Exception] = None

        if not isinstance(obj, dict):
            raise TypeError(f'ScrutinyClient only sends data under the form of a dictionary. Received {obj.__class__.__name__}')

        self._conn_lock.acquire()
        if self._conn is None:
            self._conn_lock.release()
            raise sdk_exceptions.ConnectionError(f"Disconnected from server")

        try:
            data = json.dumps(obj).encode(self._encoding)
            self._conn.send(data)
        except TimeoutError:
            pass
        except (websockets.exceptions.WebSocketException, socket.error) as e:
            error = e
            self._logger.debug(traceback.format_exc())
        finally:
            self._conn_lock.release()

        if error:
            self.disconnect()
            raise sdk_exceptions.ConnectionError(f"Disconnected from server. {error}")

    def _rxt_recv(self, timeout: Optional[float] = None) -> Optional[dict]:
        # No need to lock conn_lock here. Important is during disconnection
        error: Optional[Exception] = None
        obj: Optional[dict] = None

        if self._conn is None:
            raise sdk_exceptions.ConnectionError(f"Disconnected from server")

        try:
            data = self._conn.recv(timeout=timeout)
            if isinstance(data, bytes):
                data = data.decode(self._encoding)
            obj = json.loads(data)
        except TimeoutError:
            pass
        except (websockets.exceptions.WebSocketException, socket.error) as e:
            error = e
            self._logger.debug(traceback.format_exc())

        if error:
            self._rxt_disconnect()
            raise sdk_exceptions.ConnectionError(f"Disconnected from server. {error}")

        return obj

    def get(self, path: str) -> WatchableHandle:
        return WatchableHandle()

    def __del__(self):
        self.disconnect()

    @property
    def name(self) -> str:
        return '' if self._name is None else self.name

    @property
    def server_state(self) -> ServerState:
        self._state_lock.acquire()
        val = self._server_state  # Can be modified by the rxthread
        self._state_lock.release()
        return val

    @property
    def hostname(self) -> Optional[str]:
        self._state_lock.acquire()
        val = self._hostname  # Can be modified by the rxthread
        self._state_lock.release()
        return val

    @property
    def port(self) -> Optional[int]:
        self._state_lock.acquire()
        val = self._port  # Can be modified by the rxthread
        self._state_lock.release()
        return val
