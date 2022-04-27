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


from scrutiny.server.protocol import *
from scrutiny.server.device.request_dispatcher import RequestDispatcher, SuccessCallback, FailureCallback
from scrutiny.server.datastore import Datastore

from typing import Any


class DatastoreUpdater:

    logger: logging.Logger
    dispatcher: RequestDispatcher
    protocol: Protocol
    datastore: Datastore
    read_priority: int
    write_priority: int
    stop_requested: bool
    request_pending: bool
    started: bool

    def __init__(self, protocol: Protocol, dispatcher: RequestDispatcher, datastore: Datastore, read_priority: int, write_priority: int):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dispatcher = dispatcher
        self.protocol = protocol
        self.datastore = datastore
        self.read_priority = read_priority
        self.write_priority = write_priority
        self.reset()

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stop_requested = True

    def reset(self) -> None:
        self.stop_requested = False
        self.request_pending = False
        self.started = False

    def process(self) -> None:
        if not self.started:
            self.reset()
            return
        elif self.stop_requested and not self.request_pending:
            self.reset()
            return

    def success_callback(self, request: Request, response_code: ResponseCode, response_data: ResponseData, params: Any = None):
        self.logger.debug("Success callback. Request=%s. Response Code=%s, Params=%s" % (request, response_code, params))

        if response_code == ResponseCode.OK:
            pass  # todo
        else:
            pass  # todo

        self.completed()

    def failure_callback(self, request: Request, params: Any = None) -> None:
        self.logger.debug("Failure callback. Request=%s. Params=%s" % (request, params))
        pass    # todo

        self.completed()

    def completed(self) -> None:
        self.request_pending = False
