#    memory_writer.py
#        Synchronize the datastore with the device
#        Poll for entries that are watched and update the device with value change request
#        coming from the user in the datastore.
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import time
import logging
import binascii
import copy
import bisect
import traceback

from scrutiny.server.protocol import *
from scrutiny.server.device.request_dispatcher import RequestDispatcher, SuccessCallback, FailureCallback
from scrutiny.server.datastore import Datastore, DatastoreEntry

from typing import Any, List, Tuple, Optional


class MemoryWriter:

    DEFAULT_MAX_REQUEST_SIZE: int = 1024
    DEFAULT_MAX_RESPONSE_SIZE: int = 1024

    logger: logging.Logger
    dispatcher: RequestDispatcher
    protocol: Protocol
    datastore: Datastore
    request_priority: int
    stop_requested: bool
    request_pending: bool
    started: bool
    max_request_size: int
    max_response_size: int
    forbidden_regions: List[Tuple[int, int]]
    readonly_regions: List[Tuple[int, int]]

    entry_being_updated : Optional[DatastoreEntry]
    request_of_entry_being_updated : Optional[Request]
    watched_entries : List[str]
    write_cursor : int

    def __init__(self, protocol: Protocol, dispatcher: RequestDispatcher, datastore: Datastore, request_priority: int):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dispatcher = dispatcher
        self.protocol = protocol
        self.datastore = datastore
        self.request_priority = request_priority

        self.reset()

    def set_max_request_size(self, max_size: int) -> None:
        self.max_request_size = max_size

    def set_max_response_size(self, max_size: int) -> None:
        self.max_response_size = max_size

    def add_forbidden_region(self, start_addr: int, size: int) -> None:
        self.forbidden_regions.append((start_addr, size))

    def add_readonly_region(self, start_addr: int, size: int) -> None:
        self.readonly_regions.append((start_addr, size))

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

        self.watched_entries = []
        self.write_cursor = 0
        self.entry_being_updated = None
        self.request_of_entry_being_updated = None

    def process(self) -> None:
        if not self.started:
            self.reset()
            return
        elif self.stop_requested and not self.request_pending:
            self.reset()
            return

        if not self.request_pending:
            request = self.make_next_write_request()
            if request is not None:
                self.logger.debug('Registering a MemoryWrite request. %s' % (request))
                self.dispatcher.register_request(
                    request=request,
                    success_callback=SuccessCallback(self.success_callback),
                    failure_callback=FailureCallback(self.failure_callback),
                    priority=self.request_priority
                )
                self.request_pending = True

    def make_next_write_request(self) -> Optional[Request]:
        request:Optional[Request] = None

        if self.write_cursor >= len(self.watched_entries):
            self.watched_entries = self.datastore.get_watched_entries_id()
            self.write_cursor = 0

        if self.entry_being_updated is None:
            while self.write_cursor < len(self.watched_entries):
                entry = self.datastore.get_entry(self.watched_entries[self.write_cursor])
                self.write_cursor +=1
                if entry.has_pending_target_update():
                    self.entry_being_updated = entry
                    break

        if self.entry_being_updated is not None:
            value_to_write = self.entry_being_updated.get_pending_target_update_val()
            if value_to_write is None:
                self.logger.critical('Value to write is not availble. This should never happen')
            else:
                encoded_value, write_mask = self.entry_being_updated.encode_pending_update_value() 
                request = self.protocol.write_single_memory_block(address=self.entry_being_updated.get_address(), data=encoded_value, write_mask=write_mask)
                self.request_of_entry_being_updated = request
        return request

    def success_callback(self, request: Request, response: Response, params: Any = None) -> None:
        self.logger.debug("Success callback. Response=%s, Params=%s" % (response, params))

        if response.code == ResponseCode.OK:
            if request == self.request_of_entry_being_updated:
                request_data = self.protocol.parse_request(request)
                if request_data['valid']:
                    response_data = self.protocol.parse_response(response)
                    if response_data['valid'] :
                        if self.entry_being_updated is not None and self.entry_being_updated.has_pending_target_update():
                            response_match_request = True
                            if len(request_data['blocks_to_write']) != 1 or len(response_data['written_blocks']) != 1:
                                response_match_request = False
                            else:
                                if request_data['blocks_to_write'][0]['address'] != response_data['written_blocks'][0]['address']:
                                    response_match_request = False
                                
                                if len(request_data['blocks_to_write'][0]['data']) != response_data['written_blocks'][0]['length']:
                                    response_match_request = False

                            if response_match_request:
                                newval, mask = self.entry_being_updated.encode_pending_update_value()
                                self.entry_being_updated.set_value_from_data(newval)
                                self.entry_being_updated.mark_target_update_request_complete()
                            else:
                                self.logger.error('Received a WriteMemory response that does not match the request')
                        else:
                            self.logger.warning('Received a WriteMemory response but no datastore entry was being updated.')
                    else:
                        self.logger.error('Response for WriteMemory request is malformed and must be discared.')
                else:
                    self.logger.error('Request associated with WriteMemory response is malformed. Response must be discared.')
            else:
                self.logger.critical('Received a WriteMemory response for the wrong request. This should not happen')
        else:
            self.logger.warning('Response for WriteMemory has been refused with response code %s.' % response.code)

        self.completed()

    def failure_callback(self, request: Request, params: Any = None) -> None:
        self.logger.debug("Failure callback. Request=%s. Params=%s" % (request, params))
        self.logger.error('Failed to get a response for WriteMemory request.')

        if self.entry_being_updated is not None:
            self.entry_being_updated.mark_target_update_request_failed()

        self.completed()

    def completed(self) -> None:
        self.request_pending = False
        self.entry_being_updated = None
        self.request_of_entry_being_updated = None
