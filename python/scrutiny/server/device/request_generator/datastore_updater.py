#    datastore_updater.py
#        Synchronize the datastore with the device
#        Poll for entries that are watched. Write entries marked for write.
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import time
import logging
import binascii

from scrutiny.server.protocol import ResponseCode


class DatastoreUpdater:

    def __init__(self, protocol, dispatcher, datastore, read_priority=0, write_priority=0):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dispatcher = dispatcher
        self.protocol = protocol
        self.datastore = datastore
        self.read_priority = read_priority
        self.write_priority = write_priority
        self.reset()

    def start(self):
        self.started = True

    def stop(self):
        self.stop_requested = True

    def reset(self):
        self.stop_requested = False
        self.request_pending = False
        self.started = False

    def process(self):
        if not self.started:
            self.reset()
            return
        elif self.stop_requested and not self.request_pending:
            self.reset()
            return

    def success_callback(self, request, response_code, response_data, params=None):
        self.logger.debug("Success callback. Request=%s. Response Code=%s, Params=%s" % (request, response_code, params))

        if response_code == ResponseCode.OK:
            pass
        else:
            pass

        self.completed()

    def failure_callback(self, request, params=None):
        self.logger.debug("Failure callback. Request=%s. Params=%s" % (request, params))
        pass
        self.completed()

    def completed(self):
        self.request_pending = False
