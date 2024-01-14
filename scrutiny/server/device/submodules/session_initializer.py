#    session_initializer.py
#        Once enabled, try to establish a working session with a device.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import logging
from time import time
import traceback

from scrutiny.server.protocol import *
import scrutiny.server.protocol.typing as protocol_typing
from scrutiny.server.device.request_dispatcher import RequestDispatcher, SuccessCallback, FailureCallback

from typing import Optional, Any, cast


class SessionInitializer:
    """
    Try to establish a connection with a device by sending Connects requests.
    If it succeeds, will make the session ID available to the Device Handler and report the success.
    If the device refuse the connection, retry. If communication is broken, go to error state
    """

    logger: logging.Logger
    dispatcher: RequestDispatcher   # We put the request in here, and we know they'll go out
    protocol: Protocol              # The actual protocol. Used to build the request payloads
    priority: int                   # Our dispatcher priority
    connection_pending: bool        # Indicates that a request is out, we're waiting for a response
    stop_requested: bool            # Indicates that the user wants to stop trying to connect.
    started: bool   # Indicates that SessionInitializer is enabled and will actively try to connect to a device
    last_connect_sent: Optional[float]  # timestamp of the last request sent to a device.
    success: bool   # Indicates the we succeeded in connecting to a device
    error: bool     # Indicates that we failed to connect to a device, because something went wrong (request timeout or bad data)
    session_id: Optional[int]   # Session ID given by the device when a connection is accepted

    RECONNECT_DELAY: float = 1.0    # Retry interval if a device refuse the connection

    def __init__(self, protocol: Protocol, dispatcher: RequestDispatcher, priority: int):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dispatcher = dispatcher
        self.protocol = protocol
        self.priority = priority
        self.reset()

    def start(self) -> None:
        """Enable the session initializer to try to establish a connection"""
        self.started = True
        self.stop_requested = False

    def stop(self) -> None:
        """Stops the session initializer from trying to establish a connection"""
        self.logger.debug('Stop requested')
        self.stop_requested = True

    def fully_stopped(self) -> bool:
        return self.started == False and self.stop_requested == False

    def reset(self) -> None:
        """Put back the session initializer to its startup state"""
        self.connection_pending = False
        self.stop_requested = False
        self.started = False
        self.last_connect_sent = None
        self.success = False
        self.error = False
        self.session_id = None

    def connection_successful(self) -> bool:
        """Indicates that a device accepted a Connect request"""
        return self.success

    def is_in_error(self) -> bool:
        """Indicates that something went wrong with the communication with the device"""
        return self.error

    def get_session_id(self) -> Optional[int]:
        """Returns the session ID given by the device when the Connect request was accepted. 
        None if no request was accepted yet"""
        return self.session_id

    def process(self) -> None:
        """To be called periodically"""
        if not self.started:
            self.reset()
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
        """Callback called by the request dispatcher when a request succeeds to complete"""
        if response.code == ResponseCode.OK:
            try:
                response_data = cast(protocol_typing.Response.CommControl.Connect, self.protocol.parse_response(response))
                self.logger.info('The connection request was accepted by the device')
                self.session_id = response_data['session_id']
                self.success = True
            except Exception:
                self.logger.warning('Connection request to the device was acknowledged by the device but response data was malformed')
                self.logger.debug(traceback.format_exc())
                self.error = True
        else:
            self.logger.warning('Connection request to the device was refused by the device with response code %s' % response.code)
        self.completed()

    def failure_callback(self, request: Request, params: Any = None) -> None:
        """Callback called by the request dispatcher when a request fails to complete"""
        self.logger.error('The connection request to device did not complete')
        self.error = True

        self.completed()

    def completed(self) -> None:
        """Common code after success or failure callback"""
        self.connection_pending = False
        if self.stop_requested:
            self.reset()
