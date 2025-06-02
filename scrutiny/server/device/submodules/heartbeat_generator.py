#    heartbeat_generator.py
#        Once enabled, generate HEARTBEAT request periodically to keep a connection alive
#        with a device.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

__all__ = ['HeartbeatGenerator']

import time
import logging

from scrutiny.server.protocol import *
import scrutiny.server.protocol.typing as protocol_typing
from scrutiny.server.device.request_dispatcher import RequestDispatcher
from scrutiny import tools
from scrutiny.tools.typing import *


class HeartbeatGenerator:
    """
    Poll the device with periodic heartbeat message to know if it is still there and alive.
    """
    logger: logging.Logger
    dispatcher: RequestDispatcher   # We put the request in here, and we know they'll go out
    protocol: Protocol              # The actual protocol. Used to build the request payloads
    priority: int                   # Our dispatcher priority
    session_id: Optional[int]       # The session ID to include in the heartbeat request
    last_heartbeat_request: Optional[float]     # Time at which that last heartbeat request has been sent.
    last_heartbeat_timestamp: Optional[float]   # Time at which the last successful heartbeat response has been received
    challenge: int      # The computation challenge included in the pending request.
    interval: float     # Heartbeat interval in seconds
    pending: bool       # True when a request is sent and we are waiting for a response
    started: bool       # True when started. Sends heartbeat only when started, otherwise keep silent

    def __init__(self, protocol: Protocol, dispatcher: RequestDispatcher, priority: int):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dispatcher = dispatcher
        self.protocol = protocol
        self.session_id = None
        self.last_heartbeat_request = None
        self.last_heartbeat_timestamp = time.monotonic()
        self.challenge = 0
        self.interval = 3
        self.priority = priority
        self.reset()

    def set_interval(self, interval: float) -> None:
        """Set the interval of time at which to send heartbeat"""
        self.interval = interval

    def set_session_id(self, session_id: int) -> None:
        """Sets the session ID to use for heartbeat request"""
        self.session_id = session_id

    def start(self) -> None:
        """Enable the heartbeat generator."""
        self.started = True
        self.last_heartbeat_timestamp = time.monotonic()

    def stop(self) -> None:
        """Disable the heartbeat generator. Will stop sending request and FSM will go idle"""
        self.logger.debug('Stop requested')
        self.started = False

    def fully_stopped(self) -> bool:
        """Indicates that this submodule is stopped and has no pending state"""
        return self.started == False

    def reset(self) -> None:
        """Put the heartbeat generator in its startup state"""
        self.pending = False
        self.started = False
        self.session_id = None

    def process(self) -> None:
        """To be called periodically"""
        if not self.started:
            self.reset()
            return

        # If no request is being waited and we have a session ID assigned
        if self.pending == False and self.session_id is not None:
            if self.last_heartbeat_request is None or (time.monotonic() - self.last_heartbeat_request > self.interval):
                if self.logger.isEnabledFor(logging.DEBUG):  # pragma: no cover
                    self.logger.debug('Registering a Heartbeat request')
                self.dispatcher.register_request(
                    request=self.protocol.comm_heartbeat(session_id=self.session_id, challenge=self.challenge),
                    success_callback=self.success_callback,
                    failure_callback=self.failure_callback,
                    priority=self.priority
                )
                self.pending = True
                self.last_heartbeat_request = time.monotonic()

    def success_callback(self, request: Request, response: Response, params: Any = None) -> None:
        """ Called by the dispatcher when a request is completed and succeeded"""
        if self.logger.isEnabledFor(logging.DEBUG):  # pragma: no cover
            self.logger.debug("Success callback. Request=%s. Response Code=%s, Params=%s" % (request, response.code, params))

        expected_challenge_response = self.protocol.heartbeat_expected_challenge_response(self.challenge)
        if self.started:
            if response.code == ResponseCode.OK:
                try:
                    response_data = cast(protocol_typing.Response.CommControl.Heartbeat, self.protocol.parse_response(response))

                    if response_data['session_id'] == self.session_id:
                        if response_data['challenge_response'] == expected_challenge_response:  # Make sure the device is not sending a buffered response
                            self.last_heartbeat_timestamp = time.monotonic()  # This is the indicator that the device is alive
                        else:
                            self.logger.error('Heartbeat challenge response is not good. Got %s, expected %s' %
                                              (response_data['challenge_response'], expected_challenge_response))
                    else:
                        self.logger.error('Heartbeat session ID echo not good. Got %s, expected %s' % (response_data['session_id'], self.session_id))
                except Exception as e:
                    tools.log_exception(self.logger, e, 'Heartbeat response data is invalid')
            else:
                self.logger.error('Heartbeat request got Nacked. %s' % response.code)

        self.completed()

    def failure_callback(self, request: Request, params: Any = None) -> None:
        """ Called by the dispatcher when a request is completed and failed to succeed"""
        if self.logger.isEnabledFor(logging.DEBUG):  # pragma: no cover
            self.logger.debug("Failure callback. Request=%s. Params=%s" % (request, params))
        self.completed()

    def completed(self) -> None:
        """ Common code between success and failure"""
        self.challenge = (self.challenge + 1) & 0xFFFF  # Next challenge
        self.pending = False
