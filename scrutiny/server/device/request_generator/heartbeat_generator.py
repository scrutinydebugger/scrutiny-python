#    heartbeat_generator.py
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import time
import logging

from scrutiny.server.protocol import *
from scrutiny.server.device.request_dispatcher import RequestDispatcher, SuccessCallback, FailureCallback

from typing import Any, Optional


class HeartbeatGenerator:

    logger: logging.Logger
    dispatcher: RequestDispatcher
    protocol: Protocol
    session_id: Optional[int]
    last_heartbeat_request: Optional[float]
    last_heartbeat_timestamp: Optional[float]
    challenge: int
    interval: float
    priority: int
    pending: bool
    started: bool

    def __init__(self, protocol: Protocol, dispatcher: RequestDispatcher, priority: int):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dispatcher = dispatcher
        self.protocol = protocol
        self.session_id = None
        self.last_heartbeat_request = None
        self.last_heartbeat_timestamp = time.time()
        self.challenge = 0
        self.interval = 3
        self.priority = priority
        self.reset()

    def set_interval(self, interval: float) -> None:
        self.interval = interval

    def set_session_id(self, session_id: Optional[int]) -> None:
        assert session_id is not None
        self.session_id = session_id

    def start(self) -> None:
        self.started = True
        self.last_heartbeat_timestamp = time.time()

    def stop(self) -> None:
        self.started = False

    def reset(self) -> None:
        self.pending = False
        self.started = False

    def last_valid_heartbeat_timestamp(self) -> Optional[float]:
        return self.last_heartbeat_timestamp

    def process(self) -> None:
        if not self.started:
            self.reset()
            return

        if self.pending == False and self.session_id is not None:
            if self.last_heartbeat_request is None or (time.time() - self.last_heartbeat_request > self.interval):
                self.logger.debug('Registering a Heartbeat request')
                self.dispatcher.register_request(
                    request=self.protocol.comm_heartbeat(session_id=self.session_id, challenge=self.challenge),
                    success_callback=SuccessCallback(self.success_callback),
                    failure_callback=FailureCallback(self.failure_callback),
                    priority=self.priority
                )
                self.pending = True
                self.last_heartbeat_request = time.time()

    def success_callback(self, request: Request, response: Response, params: Any = None) -> None:
        self.logger.debug("Success callback. Request=%s. Response Code=%s, Params=%s" % (request, response.code, params))

        expected_challenge_response = self.protocol.heartbeat_expected_challenge_response(self.challenge)
        if response.code == ResponseCode.OK:
            response_data = self.protocol.parse_response(response)
            if response_data['valid']:
                if response_data['session_id'] == self.session_id:
                    if response_data['challenge_response'] == expected_challenge_response:
                        self.last_heartbeat_timestamp = time.time()
                    else:
                        self.logger.error('Heartbeat challenge response is not good. Got %s, expected %s' %
                                          (response_data['challenge_response'], expected_challenge_response))
                else:
                    self.logger.error('Heartbeat session ID echo not good. Got %s, expected %s' % (response_data['session_id'], self.session_id))
            else:
                self.logger.error('Heartbeat response data is invalid')
        else:
            self.logger.error('Heartbeat request got Nacked. %s' % response.code)

        self.completed()

    def failure_callback(self, request: Request, params: Any = None) -> None:
        self.logger.debug("Failure callback. Request=%s. Params=%s" % (request, params))
        self.completed()

    def completed(self) -> None:
        self.challenge = (self.challenge + 1) & 0xFFFF
        self.pending = False
