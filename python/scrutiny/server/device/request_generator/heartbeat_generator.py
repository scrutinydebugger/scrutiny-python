#    heartbeat_generator.py
#        Once enabled, generate HEARTBEAT request periodically to keep a connection alive
#        with a device.
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import time
import logging

from scrutiny.server.protocol import ResponseCode


class HeartbeatGenerator:

    def __init__(self, protocol, dispatcher, priority=0):
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

    def set_interval(self, interval):
        self.interval = interval

    def set_session_id(self, session_id):
        self.session_id = session_id

    def start(self):
        self.started = True
        self.last_heartbeat_timestamp = time.time()

    def stop(self):
        self.started = False

    def reset(self):
        self.pending = False
        self.started = False

    def last_valid_heartbeat_timestamp(self):
        return self.last_heartbeat_timestamp

    def process(self):
        if not self.started:
            self.reset()
            return

        if self.pending == False:
            if self.last_heartbeat_request is None or (time.time() - self.last_heartbeat_request > self.interval):
                self.logger.debug('Registering a Heartbeat request')
                self.dispatcher.register_request(
                    request=self.protocol.comm_heartbeat(session_id=self.session_id, challenge=self.challenge),
                    success_callback=self.success_callback,
                    failure_callback=self.failure_callback,
                    priority=self.priority
                )
                self.pending = True
                self.last_heartbeat_request = time.time()

    def success_callback(self, request, response_code, response_data, params=None):
        self.logger.debug("Success callback. Request=%s. Response Code=%s, Params=%s" % (request, response_code, params))
        expected_challenge_response = self.protocol.heartbeat_expected_challenge_response(self.challenge)

        if response_code == ResponseCode.OK:
            if response_data['session_id'] == self.session_id:
                if response_data['challenge_response'] == expected_challenge_response:
                    self.last_heartbeat_timestamp = time.time()
                else:
                    self.logger.error('Heartbeat challenge response is not good. Got %s, expected %s' %
                                      (response_data['challenge_response'], expected_challenge_response))
            else:
                self.logger.error('Heartbeat session ID echo not good. Got %s, expected %s' % (response_data['session_id'], self.session_id))
        else:
            self.logger.error('Heartbeat request got Nacked. %s' % response_code)

        self.completed()

    def failure_callback(self, request, params=None):
        self.logger.debug("Failure callback. Request=%s. Params=%s" % (request, params))
        self.completed()

    def completed(self):
        self.challenge = (self.challenge + 1) & 0xFFFF
        self.pending = False
