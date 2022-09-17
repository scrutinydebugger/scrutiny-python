#    memory_writer.py
#        Synchronize the datastore with the device
#        Poll for entries that are watched and update the device with value change request
#        coming from the user in the datastore.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import logging
from scrutiny.server.datastore.datastore_entry import DatastoreRPVEntry, DatastoreVariableEntry, EntryType

from scrutiny.server.protocol import *
import scrutiny.server.protocol.commands as cmd
import scrutiny.server.protocol.typing as protocol_typing
from scrutiny.server.device.request_dispatcher import RequestDispatcher, SuccessCallback, FailureCallback
from scrutiny.server.datastore import Datastore, DatastoreEntry

from typing import Any, List, Tuple, Optional, cast


class MemoryWriter:

    DEFAULT_MAX_REQUEST_PAYLOAD_SIZE: int = 1024
    DEFAULT_MAX_RESPONSE_PAYLOAD_SIZE: int = 1024

    logger: logging.Logger
    dispatcher: RequestDispatcher
    protocol: Protocol
    datastore: Datastore
    request_priority: int
    stop_requested: bool
    request_pending: bool
    started: bool
    max_request_payload_size: int
    max_response_payload_size: int
    forbidden_regions: List[Tuple[int, int]]
    readonly_regions: List[Tuple[int, int]]

    entry_being_updated: Optional[DatastoreEntry]
    request_of_entry_being_updated: Optional[Request]
    watched_entries: List[str]
    write_cursor: int

    def __init__(self, protocol: Protocol, dispatcher: RequestDispatcher, datastore: Datastore, request_priority: int):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dispatcher = dispatcher
        self.protocol = protocol
        self.datastore = datastore
        self.request_priority = request_priority

        self.reset()

    def set_max_request_payload_size(self, max_size: int) -> None:
        self.max_request_payload_size = max_size

    def set_max_response_payload_size(self, max_size: int) -> None:
        self.max_response_payload_size = max_size

    def set_size_limits(self, max_request_payload_size: int, max_response_payload_size: int) -> None:
        self.set_max_request_payload_size(max_request_payload_size)
        self.set_max_response_payload_size(max_response_payload_size)

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

        self.max_request_payload_size = self.DEFAULT_MAX_REQUEST_PAYLOAD_SIZE
        self.max_response_payload_size = self.DEFAULT_MAX_RESPONSE_PAYLOAD_SIZE
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
            request = self.make_next_memory_write_request()
            if request is not None:
                self.logger.debug('Registering a MemoryWrite request. %s' % (request))
                self.dispatcher.register_request(
                    request=request,
                    success_callback=SuccessCallback(self.success_callback),
                    failure_callback=FailureCallback(self.failure_callback),
                    priority=self.request_priority
                )
                self.request_pending = True

    def make_next_memory_write_request(self) -> Optional[Request]:
        request: Optional[Request] = None

        if self.write_cursor >= len(self.watched_entries):
            self.watched_entries = self.datastore.get_watched_entries_id(EntryType.Var)
            self.watched_entries += self.datastore.get_watched_entries_id(EntryType.RuntimePublishedValue)
            self.write_cursor = 0

        if self.entry_being_updated is None:
            while self.write_cursor < len(self.watched_entries):
                entry = self.datastore.get_entry(self.watched_entries[self.write_cursor])
                self.write_cursor += 1
                if entry.has_pending_target_update():
                    self.entry_being_updated = entry
                    break

        if self.entry_being_updated is not None:
            value_to_write = self.entry_being_updated.get_pending_target_update_val()
            if value_to_write is None:
                self.logger.critical('Value to write is not availble. This should never happen')
            else:
                if isinstance(self.entry_being_updated, DatastoreVariableEntry):
                    encoded_value, write_mask = self.entry_being_updated.encode(value_to_write)
                    request = self.protocol.write_single_memory_block(
                        address=self.entry_being_updated.get_address(),
                        data=encoded_value,
                        write_mask=write_mask
                    )
                elif isinstance(self.entry_being_updated, DatastoreRPVEntry):
                    request = self.protocol.write_runtime_published_values((self.entry_being_updated.get_rpv().id, value_to_write))
                else:
                    raise RuntimeError('entry_being_updated should be of type %s' % self.entry_being_updated.__class__.__name__)
                self.request_of_entry_being_updated = request
        return request

    def success_callback(self, request: Request, response: Response, params: Any = None) -> None:
        self.logger.debug("Success callback. Response=%s, Params=%s" % (response, params))
        subfn = cmd.MemoryControl.Subfunction(response.subfn)
        if subfn == cmd.MemoryControl.Subfunction.Write:
            self.success_callback_memory_write(request, response, params)
        elif subfn == cmd.MemoryControl.Subfunction.WriteRPV:
            self.success_callback_rpv_write(request, response, params)
        else:
            self.logger.critical('Got a response for a request we did not send. Not supposed to happen!')

        self.completed()

    def success_callback_memory_write(self, request: Request, response: Response, params: Any = None) -> None:
        if response.code == ResponseCode.OK:
            if request == self.request_of_entry_being_updated:
                request_data = cast(protocol_typing.Request.MemoryControl.Write, self.protocol.parse_request(request))
                response_data = cast(protocol_typing.Response.MemoryControl.Write, self.protocol.parse_response(response))

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
                self.logger.critical('Received a WriteMemory response for the wrong request. This should not happen')
        else:
            self.logger.warning('Response for WriteMemory has been refused with response code %s.' % response.code)

    def success_callback_rpv_write(self, request: Request, response: Response, params: Any = None) -> None:
        self.logger.debug("Success callback. Response=%s, Params=%s" % (response, params))

        if response.code == ResponseCode.OK:
            if request == self.request_of_entry_being_updated:
                request_data = cast(protocol_typing.Request.MemoryControl.WriteRPV, self.protocol.parse_request(request))
                response_data = cast(protocol_typing.Response.MemoryControl.WriteRPV, self.protocol.parse_response(response))

                if self.entry_being_updated is not None and self.entry_being_updated.has_pending_target_update():
                    response_match_request = True
                    if len(request_data['rpvs']) != 1 or len(response_data['written_rpv']) != 1:
                        response_match_request = False
                    else:
                        if request_data['rpvs'][0]['id'] != response_data['written_rpv'][0]['id']:
                            response_match_request = False

                    if response_match_request:
                        newval = self.entry_being_updated.get_pending_target_update_val()
                        self.entry_being_updated.set_value(newval)
                        self.entry_being_updated.mark_target_update_request_complete()
                    else:
                        self.logger.error('Received a WriteRPV response that does not match the request')
                else:
                    self.logger.warning('Received a WriteRPV response but no datastore entry was being updated.')
            else:
                self.logger.critical('Received a WriteRPV response for the wrong request. This should not happen')
        else:
            self.logger.warning('Response for WriteRPV has been refused with response code %s.' % response.code)

    def failure_callback(self, request: Request, params: Any = None) -> None:
        self.logger.debug("Failure callback. Request=%s. Params=%s" % (request, params))

        subfn = cmd.MemoryControl.Subfunction(request.subfn)
        if subfn == cmd.MemoryControl.Subfunction.Write:
            self.logger.error('Failed to get a response for WriteMemory request.')
        elif subfn == cmd.MemoryControl.Subfunction.WriteRPV:
            self.logger.error('Failed to get a response for WriteRPV request.')
        else:
            self.logger.critical('Got a response for a request we did not send. Not supposed to happen!')

        if self.entry_being_updated is not None:
            self.entry_being_updated.mark_target_update_request_failed()

        self.completed()

    def completed(self) -> None:
        self.request_pending = False
        self.entry_being_updated = None
        self.request_of_entry_being_updated = None
