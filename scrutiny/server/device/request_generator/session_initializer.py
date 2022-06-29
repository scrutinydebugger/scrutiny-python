#    session_initializer.py
#        Once enabled, try to establish a working session with a device.
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import logging
from time import time

from scrutiny.server.protocol import *
from scrutiny.server.device.request_dispatcher import RequestDispatcher, SuccessCallback, FailureCallback

from typing import Optional, Any


class SessionInitializer:

    logger: logging.Logger
    dispatcher: RequestDispatcher
    protocol: Protocol
    priority: int
    connection_pending: bool
    stop_requested: bool
    started: bool
    last_connect_sent: Optional[float]
    success: bool
    error: bool
    session_id: Optional[int]

    RECONNECT_DELAY: float = 1.0

    def __init__(self, protocol: Protocol, dispatcher: RequestDispatcher, priority: int):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dispatcher = dispatcher
        self.protocol = protocol
        self.priority = priority
        self.reset()

    def start(self) -> None:
        self.started = True
        self.stop_requested = False

    def stop(self) -> None:
        self.stop_requested = True

    def reset(self) -> None:
        self.connection_pending = False
        self.stop_requested = False
        self.started = False
        self.last_connect_sent = None
        self.success = False
        self.error = False
        self.session_id = None

    def connection_successful(self) -> bool:
        return self.success

    def is_in_error(self) -> bool:
        return self.error

    def get_session_id(self) -> Optional[int]:
        return self.session_id

    def process(self) -> None:
        if not self.started:
            return
        if self.error:
            if self.stop_requested:
                self.reset()
            return

        if not self.connection_pending and self.stop_requested:
            self.reset()
            return

        if not self.connection_pending and (self.last_connect_sent is None or time() - self.last_connect_sent > self.RECONNECT_DELAY):
            self.success = False
            self.last_connect_sent = time()
            self.logger.debug('Registering a Connect request')
            self.dispatcher.register_request(request=self.protocol.comm_connect(),
                                             success_callback=SuccessCallback(self.success_callback),
                                             failure_callback=FailureCallback(self.failure_callback),
                                             priority=self.priority)
            self.connection_pending = True

    def success_callback(self, request: Request, response: Response, params: Any = None) -> None:
        if response.code == ResponseCode.OK:
            response_data = self.protocol.parse_response(response)
            if response_data['valid']:
                self.logger.info('The connection request was accepted by the device')
                self.session_id = response_data['session_id']
                self.success = True
            else:
                self.logger.warning('Connection request to the device was acknowledged by the device but response data was malformed')
                self.error = True
        else:
            self.logger.warning('Connection request to the device was refused by the device with response code %s' % response.code)
        self.completed()

    def failure_callback(self, request: Request, params: Any = None) -> None:
        self.logger.error('The connection request to device did not complete')
        self.error = True

        self.completed()

    def completed(self) -> None:
        self.connection_pending = False
        if self.stop_requested:
            self.reset()
