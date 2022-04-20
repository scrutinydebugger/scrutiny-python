#    session_initializer.py
#        Once enabled, try to establish a working session with a device.
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import time
import logging
from time import time

from scrutiny.server.protocol import ResponseCode


class SessionInitializer:

    RECONNECT_DELAY = 1.0

    def __init__(self, protocol, dispatcher, priority=0):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dispatcher = dispatcher
        self.protocol = protocol
        self.priority = priority
        self.reset()

    def start(self):
        self.started = True
        self.stop_requested = False

    def stop(self):
        self.stop_requested = True

    def reset(self):
        self.connection_pending = False
        self.stop_requested = False
        self.started = False
        self.last_connect_sent = None
        self.success = False
        self.error = False
        self.session_id = None

    def connection_successful(self):
        return self.success

    def is_in_error(self):
        return self.error

    def get_session_id(self):
        return self.session_id

    def process(self):
        if not self.started or self.error:
            return
        elif not self.connection_pending and self.stop_requested:
            self.reset()
            return

        if not self.connection_pending and (self.last_connect_sent is None or time() - self.last_connect_sent > self.RECONNECT_DELAY):
            self.success = False
            self.last_connect_sent = time()
            self.logger.debug('Registering a Connect request')
            self.dispatcher.register_request(request=self.protocol.comm_connect(),
                                             success_callback=self.success_callback, failure_callback=self.failure_callback, priority=self.priority)
            self.connection_pending = True

    def success_callback(self, request, response_code, response_data, params=None):
        if response_code == ResponseCode.OK:
            if response_data['valid']:
                self.logger.info('Connection was accepted by device')
                self.session_id = response_data['session_id']
                self.success = True
            else:
                self.logger.warning('Connection was acknowledged by device but response data was malformed')
                self.error = True
        else:
            self.logger.warning('Connection was refused by device with response code %s' % response_code)
        self.completed()

    def failure_callback(self, request, params=None):
        self.logger.error('Connection request did not complete')
        self.error = True

        self.completed()

    def completed(self):
        self.connection_pending = False
        if self.stop_requested:
            self.reset()
