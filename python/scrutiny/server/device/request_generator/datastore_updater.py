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
import copy

from scrutiny.server.protocol import *
from scrutiny.server.device.request_dispatcher import RequestDispatcher, SuccessCallback, FailureCallback
from scrutiny.server.datastore import Datastore, WatchCallback
from scrutiny.core.memory_content import MemoryContent

from typing import Any, List, Tuple


class DatastoreUpdater:

    DEFAULT_MAX_REQUEST_SIZE:int = 1024
    DEFAULT_MAX_RESPONSE_SIZE:int = 1024

    logger: logging.Logger
    dispatcher: RequestDispatcher
    protocol: Protocol
    datastore: Datastore
    read_priority: int
    write_priority: int
    stop_requested: bool
    request_pending: bool
    started: bool
    region_to_read : List
    memcontent : MemoryContent
    max_request_size:int
    max_response_size:int
    region_to_read_list:List[Tuple[int,int]]
    forbidden_regions:List[Tuple[int,int]]
    readonly_regions:List[Tuple[int,int]]
    read_request_list_valid:bool
    read_request_list:List[Request]
    read_request_queue:List[Request]

    def __init__(self, protocol: Protocol, dispatcher: RequestDispatcher, datastore: Datastore, read_priority: int, write_priority: int):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dispatcher = dispatcher
        self.protocol = protocol
        self.datastore = datastore
        self.read_priority = read_priority
        self.write_priority = write_priority
        self.memcontent = MemoryContent(retain_data = False)    # Will agglomerate contiguous blocks of data
        self.datastore.add_watch_callback(WatchCallback(self.the_watch_callback))
        self.datastore.add_unwatch_callback(WatchCallback(self.the_unwatch_callback))

        self.reset()

    def set_max_request_size(self, max_size:int):
        self.max_request_size = max_size

    def set_max_response_size(self, max_size:int):
        self.max_response_size = max_size

    def add_forbidden_region(self, start_addr:int, size:int):
        self.forbidden_regions.append((start_addr, size))

    def add_readonly_region(self, start_addr:int, size:int):
        self.readonly_regions.append((start_addr, size))

    def the_watch_callback(self, entry_id:str):
        entry = self.datastore.get_entry(entry_id)
        self.memcontent.add_empty(entry.get_address(), entry.get_size())
        self.read_request_list_valid = False

    def the_unwatch_callback(self, entry_id:str):
        entry = self.datastore.get_entry(entry_id)
        self.memcontent.delete(entry.get_address(), entry.get_size())
        self.read_request_list_valid = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stop_requested = True

    def reset(self) -> None:
        self.stop_requested = False
        self.request_pending = False
        self.started = False

        self.max_request_size = self.DEFAULT_MAX_REQUEST_SIZE
        self.max_response_size = self.DEFAULT_MAX_RESPONSE_SIZE
        self.forbidden_regions = []
        self.readonly_regions = []
        self.read_request_list_valid = False
        self.read_request_list = []
        self.read_request_queue = []

    def process(self) -> None:
        if not self.started:
            self.reset()
            return
        elif self.stop_requested and not self.request_pending:
            self.reset()
            return

        if not self.request_pending:
            if len(self.read_request_queue) == 0:
                
                if not self.read_request_list_valid:
                    self.rebuild_read_request_list()

                self.read_request_queue = copy.copy(self.read_request_list)
            else:
                pass


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

    # TODO TODO  : Rendu ici!!
    def rebuild_read_request_list(self):
        # Extract memcontent clusters
        # Split by response size then by request size
        # Generate bunch of request.  
        # Protocol must be able to provide size given a cluster.


        # todo : unittest for callbacks. Add watch, makesure self.memcontent has good clusters.
        pass    
