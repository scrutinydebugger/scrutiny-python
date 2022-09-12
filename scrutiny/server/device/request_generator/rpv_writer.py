#    rpv_writer.py
#        Make requests to read Runtime Published values from the device.
#        This feature requires a different protocol message than Memory Read
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import logging

from scrutiny.server.protocol import *
import scrutiny.server.protocol.typing as protocol_typing
from scrutiny.server.device.request_dispatcher import RequestDispatcher, SuccessCallback, FailureCallback
from scrutiny.server.datastore import Datastore, DatastoreEntry, DatastoreRPVEntry, EntryType


from typing import Any, List, Tuple, Optional, cast


class RPVWriter:

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
                self.logger.debug('Registering a RPVWrite request. %s' % (request))
                self.dispatcher.register_request(
                    request=request,
                    success_callback=SuccessCallback(self.success_callback),
                    failure_callback=FailureCallback(self.failure_callback),
                    priority=self.request_priority
                )
                self.request_pending = True

    def make_next_write_request(self) -> Optional[Request]:
        request: Optional[Request] = None

        if self.write_cursor >= len(self.watched_entries):
            self.watched_entries = self.datastore.get_watched_entries_id(EntryType.RuntimePublishedValue)
            self.write_cursor = 0

        if self.entry_being_updated is None:
            while self.write_cursor < len(self.watched_entries):
                entry = self.datastore.get_entry(self.watched_entries[self.write_cursor])
                self.write_cursor += 1
                if entry.has_pending_target_update():
                    self.entry_being_updated = entry
                    break

        if self.entry_being_updated is not None:
            resolved_entry = self.entry_being_updated.resolve()
            assert isinstance(resolved_entry, DatastoreRPVEntry)   # No RPV or Alias here! We need an address
            value_to_write = resolved_entry.get_pending_target_update_val()
            if value_to_write is None:
                self.logger.critical('Value to write is not availble. This should never happen')
            else:
                value = resolved_entry.get_pending_target_update_val()
                request = self.protocol.write_runtime_published_values((resolved_entry.get_rpv().id, value))
                self.request_of_entry_being_updated = request

        return request

    def success_callback(self, request: Request, response: Response, params: Any = None) -> None:
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

        self.completed()

    def failure_callback(self, request: Request, params: Any = None) -> None:
        self.logger.debug("Failure callback. Request=%s. Params=%s" % (request, params))
        self.logger.error('Failed to get a response for WriteRPV request.')

        if self.entry_being_updated is not None:
            self.entry_being_updated.mark_target_update_request_failed()

        self.completed()

    def completed(self) -> None:
        self.request_pending = False
        self.entry_being_updated = None
        self.request_of_entry_being_updated = None
