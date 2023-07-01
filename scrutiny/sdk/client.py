__all__ = ['Client']


from scrutiny.sdk.definitions import *
import scrutiny.sdk.exceptions as sdk_exceptions
import logging
import traceback
import socket
import websockets
import websockets.sync.client
import websockets.exceptions
import atexit


def exit_handler():
    print('My application is ending!')


from typing import *


class ScrutinyClient:

    _server_state: ServerState
    _hostname: Optional[str]
    _port: Optional[int]
    _logger: logging.Logger

    _conn: Optional[websockets.sync.client.ClientConnection]

    def __init__(self):
        self._server_state = ServerState.Disconnected
        self._hostname = None
        self._port = None
        self._conn = None
        self._logger = logging.getLogger(self.__class__.__name__)

    def connect(self, hostname: str, port: int, **kwargs) -> None:
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
        except (websockets.exceptions.WebSocketException, socket.error) as e:
            self._logger.debug(traceback.format_exc())
            connect_error = e

        if connect_error is not None:
            self.disconnect()
            raise sdk_exceptions.ConnectionError(f'Failed to connect to the server at "{uri}". Error: {connect_error}')

    def disconnect(self):
        if self._conn is not None:
            self._logger.info(f"Disconnecting from server at {self._hostname}:{self._port}")
            try:
                self._conn.close()
            except (websockets.exceptions.WebSocketException, socket.error):
                self._logger.debug("Failed to close the websocket")
                self._logger.debug(traceback.format_exc())

        self._conn = None
        self._hostname = None
        self._port = None
        self._server_state = ServerState.Disconnected

    def __del__(self):
        self.disconnect()

    @property
    def server_state(self) -> ServerState:
        return self._server_state
