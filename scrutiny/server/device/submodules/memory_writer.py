#    memory_writer.py
#        Synchronize the datastore with the device
#        Poll for entries that are watched and update the device with value change request
#        coming from the user in the datastore.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2023 Scrutiny Debugger

import logging
from scrutiny.server.datastore.datastore_entry import DatastoreRPVEntry, DatastoreVariableEntry, EntryType, UpdateTargetRequest

from scrutiny.server.protocol import *
import scrutiny.server.protocol.commands as cmd
import scrutiny.server.protocol.typing as protocol_typing
from scrutiny.server.device.request_dispatcher import RequestDispatcher, SuccessCallback, FailureCallback
from scrutiny.server.datastore.datastore import Datastore
from scrutiny.server.datastore.datastore_entry import DatastoreEntry
from scrutiny.core.codecs import Codecs, Encodable

from typing import Any, List, Tuple, Optional, cast


class MemoryWriter:

    DEFAULT_MAX_REQUEST_PAYLOAD_SIZE: int = 1024
    DEFAULT_MAX_RESPONSE_PAYLOAD_SIZE: int = 1024

    logger: logging.Logger
    dispatcher: RequestDispatcher       # We put the request in here, and we know they'll go out
    protocol: Protocol                  # The actual protocol. Used to build the request payloads
    request_priority: int               # Our dispatcher priority
    datastore: Datastore    # The datastore the look for entries to update
    stop_requested: bool    # Requested to stop polling
    request_pending: bool   # True when we are waiting for a request to complete
    started: bool           # Indicate if enabled or not
    max_request_payload_size: int   # Maximum size for a request payload gotten from the InfoPoller
    max_response_payload_size: int  # Maximum size for a response payload gotten from the InfoPoller
    forbidden_regions: List[Tuple[int, int]]    # List of memory regions to avoid. Gotten from InfoPoller
    readonly_regions: List[Tuple[int, int]]     # List of memory region that can only be read. Gotten from InfoPoller
    memory_write_allowed: bool  # Indicates if writing to memory is allowed.

    entry_being_updated: Optional[DatastoreEntry]   # The datastore entry updated by the actual pending request. None if no request is pending
    # When an entry is being written, this request is the pending request. None if nothing is being done
    request_of_entry_being_updated: Optional[Request]
    # Update request attached to the entry being updated. It's what'S coming from the API
    target_update_request_being_processed: Optional[UpdateTargetRequest]
    target_update_value_written: Optional[Encodable]

    def __init__(self, protocol: Protocol, dispatcher: RequestDispatcher, datastore: Datastore, request_priority: int):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dispatcher = dispatcher
        self.protocol = protocol
        self.datastore = datastore
        self.request_priority = request_priority

        self.reset()

    def set_max_request_payload_size(self, max_size: int) -> None:
        """Set the maximum payload size that can be sent in a request. Depends on device internal buffer size"""
        self.max_request_payload_size = max_size

    def set_max_response_payload_size(self, max_size: int) -> None:
        """Set the maximum payload size that the device can send in a response. Depends on device internal buffer size"""
        self.max_response_payload_size = max_size

    def set_size_limits(self, max_request_payload_size: int, max_response_payload_size: int) -> None:
        """Set both maximum request and response payload size"""
        self.set_max_request_payload_size(max_request_payload_size)
        self.set_max_response_payload_size(max_response_payload_size)

    def add_forbidden_region(self, start_addr: int, size: int) -> None:
        """Add a memory region to avoid touching. They normally are broadcasted by the device itself"""
        if size > 0:
            self.forbidden_regions.append((start_addr, size))
        else:
            self.logger.warning('Adding a forbidden region with non-positive size %d' % size)

    def add_readonly_region(self, start_addr: int, size: int) -> None:
        """Add a memory region tthat can only be read. We will avoid any write to them. 
        They normally are broadcasted by the device itself"""
        if size > 0:
            self.readonly_regions.append((start_addr, size))
        else:
            self.logger.warning('Adding a read only region with non-positive size %d' % size)

    def start(self) -> None:
        """Enable the memory writer to poll the datastore and update the device"""
        self.started = True

    def stop(self) -> None:
        """Stops the memory writer from polling the datastore and updating the device"""
        self.logger.debug('Stop requested')
        self.stop_requested = True

    def fully_stopped(self) -> bool:
        return self.started == False and not self.stop_requested

    def set_standby(self) -> None:
        """Put the state machine into standby and clear all internal buffers so that the logic restarts from the beginning"""
        self.stop_requested = False
        self.request_pending = False
        self.started = False

        self.entry_being_updated = None
        self.request_of_entry_being_updated = None
        self.target_update_request_being_processed = None
        self.target_update_value_written = None

    def clear_config(self) -> None:
        """Erase the configuration coming from the device handler"""
        self.max_request_payload_size = self.DEFAULT_MAX_REQUEST_PAYLOAD_SIZE
        self.max_response_payload_size = self.DEFAULT_MAX_RESPONSE_PAYLOAD_SIZE
        self.forbidden_regions = []
        self.readonly_regions = []
        self.memory_write_allowed = True

    def allow_memory_write(self, val: bool) -> None:
        self.memory_write_allowed = val

    def reset(self) -> None:
        """Put back the memory writer to its startup state"""
        self.set_standby()
        self.clear_config()

    def process(self) -> None:
        """To be called periodically"""
        if not self.started:
            self.set_standby()
            return
        elif self.stop_requested and not self.request_pending:
            self.set_standby()
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
        """
        This method generate a write request by moving in a list of watched variable entries
        It works in a round-robin scheme and will send write request 1 by 1, without agglomeration.
        It considers device internal max buffer size
        """
        request: Optional[Request] = None

        if self.entry_being_updated is None:
            while True:
                update_request = self.datastore.pop_target_update_request()

                if update_request is not None:
                    # Make sure we have the right to write to that memory region. Fails right away if we don't
                    allowed = True
                    if isinstance(update_request.entry, DatastoreVariableEntry):
                        assert update_request.entry.__class__ != DatastoreEntry  # for mypy
                        allowed = self.memory_write_allowed
                        address = update_request.entry.get_address()
                        # We don't check for bitfield size because the device will access the whole word anyway
                        size = update_request.entry.get_data_type().get_size_byte()
                        for region in self.readonly_regions:
                            if self.region_touches(address, size, region[0], region[1]):
                                allowed = False
                        for region in self.forbidden_regions:
                            if self.region_touches(address, size, region[0], region[1]):
                                allowed = False

                        if not allowed:
                            self.logger.debug("Refusing write request %s accessing address 0x%08x with size %d" %
                                              (update_request.entry.display_path, update_request.entry.get_address(), update_request.entry.get_size()))
                    if allowed:
                        self.target_update_request_being_processed = update_request
                        self.entry_being_updated = update_request.entry
                        break
                    else:
                        # Fails right away
                        update_request.complete(False)

                else:
                    break

        if self.entry_being_updated is not None and self.target_update_request_being_processed is not None:
            value_to_write = self.target_update_request_being_processed.get_value()
            if value_to_write is None:
                self.logger.critical('Value to write is not available. This should never happen')
            else:
                if isinstance(self.entry_being_updated, DatastoreVariableEntry):
                    encoding_succeeded = True
                    try:
                        value_to_write = Codecs.make_value_valid(self.entry_being_updated.get_data_type(),
                                                                 value_to_write, bitsize=self.entry_being_updated.get_bitsize())
                    except:
                        encoding_succeeded = False

                    if encoding_succeeded:
                        self.target_update_value_written = value_to_write
                        encoded_value, write_mask = self.entry_being_updated.encode(value_to_write)
                        request = self.protocol.write_single_memory_block(
                            address=self.entry_being_updated.get_address(),
                            data=encoded_value,
                            write_mask=write_mask
                        )
                    else:
                        self.target_update_value_written = None
                        self.target_update_request_being_processed.complete(success=False)
                elif isinstance(self.entry_being_updated, DatastoreRPVEntry):
                    rpv = self.entry_being_updated.get_rpv()
                    encoding_succeeded = True
                    try:
                        value_to_write = Codecs.make_value_valid(rpv.datatype, value_to_write)  # No bitsize on RPV
                    except:
                        encoding_succeeded = False
                    if encoding_succeeded:
                        self.target_update_value_written = value_to_write
                        request = self.protocol.write_runtime_published_values((rpv.id, value_to_write))
                    else:
                        self.target_update_request_being_processed.complete(success=False)
                else:
                    raise RuntimeError('entry_being_updated should be of type %s' % self.entry_being_updated.__class__.__name__)
                self.request_of_entry_being_updated = request
        return request

    def region_touches(self, address1: int, size1: int, address2: int, size2: int) -> bool:
        if size1 <= 0 or size2 <= 0:
            return False

        if address1 >= address2 + size2:
            return False

        if address2 >= address1 + size1:
            return False

        return True

    def success_callback(self, request: Request, response: Response, params: Any = None) -> None:
        """Called when a request completes and succeeds"""
        self.logger.debug("Success callback. Response=%s, Params=%s" % (response, params))
        subfn = cmd.MemoryControl.Subfunction(response.subfn)
        if subfn == cmd.MemoryControl.Subfunction.Write or subfn == cmd.MemoryControl.Subfunction.WriteMasked:
            self.success_callback_memory_write(request, response, params)
        elif subfn == cmd.MemoryControl.Subfunction.WriteRPV:
            self.success_callback_rpv_write(request, response, params)
        else:
            self.logger.critical('Got a response for a request we did not send. Not supposed to happen!')

        self.completed()

    def success_callback_memory_write(self, request: Request, response: Response, params: Any = None) -> None:
        """Called when a memory write request completes and succeeds"""
        if response.code == ResponseCode.OK:
            if request == self.request_of_entry_being_updated:
                request_data = cast(protocol_typing.Request.MemoryControl.Write, self.protocol.parse_request(request))
                response_data = cast(protocol_typing.Response.MemoryControl.Write, self.protocol.parse_response(response))

                if self.entry_being_updated is not None and self.target_update_request_being_processed is not None:
                    response_match_request = True
                    if len(request_data['blocks_to_write']) != 1 or len(response_data['written_blocks']) != 1:
                        response_match_request = False
                    else:
                        if request_data['blocks_to_write'][0]['address'] != response_data['written_blocks'][0]['address']:
                            response_match_request = False

                        if len(request_data['blocks_to_write'][0]['data']) != response_data['written_blocks'][0]['length']:
                            response_match_request = False

                    if response_match_request:
                        assert self.target_update_value_written is not None
                        self.entry_being_updated.set_value(self.target_update_value_written)
                        self.target_update_request_being_processed.complete(success=True)
                    else:
                        self.target_update_request_being_processed.complete(success=False)
                        self.logger.error('Received a WriteMemory response that does not match the request')
                else:
                    self.logger.warning('Received a WriteMemory response but no datastore entry was being updated.')
            else:
                self.logger.critical('Received a WriteMemory response for the wrong request. This should not happen')
        else:
            self.logger.warning('Response for WriteMemory has been refused with response code %s.' % response.code)

    def success_callback_rpv_write(self, request: Request, response: Response, params: Any = None) -> None:
        """Called when a RPV write request completes and succeeds"""
        self.logger.debug("Success callback. Response=%s, Params=%s" % (response, params))

        if response.code == ResponseCode.OK:
            if request == self.request_of_entry_being_updated:
                request_data = cast(protocol_typing.Request.MemoryControl.WriteRPV, self.protocol.parse_request(request))
                response_data = cast(protocol_typing.Response.MemoryControl.WriteRPV, self.protocol.parse_response(response))

                if self.entry_being_updated is not None and self.target_update_request_being_processed is not None:
                    response_match_request = True
                    if len(request_data['rpvs']) != 1 or len(response_data['written_rpv']) != 1:
                        response_match_request = False
                    else:
                        if request_data['rpvs'][0]['id'] != response_data['written_rpv'][0]['id']:
                            response_match_request = False

                    if response_match_request:
                        assert self.target_update_value_written is not None
                        self.entry_being_updated.set_value(self.target_update_value_written)
                        self.target_update_request_being_processed.complete(success=True)
                    else:
                        self.target_update_request_being_processed.complete(success=False)
                        self.logger.error('Received a WriteRPV response that does not match the request')
                else:
                    self.logger.warning('Received a WriteRPV response but no datastore entry was being updated.')
            else:
                self.logger.critical('Received a WriteRPV response for the wrong request. This should not happen')
        else:
            self.logger.warning('Response for WriteRPV has been refused with response code %s.' % response.code)

    def failure_callback(self, request: Request, params: Any = None) -> None:
        """Callback called by the request dispatcher when a request fails to complete"""
        self.logger.debug("Failure callback. Request=%s. Params=%s" % (request, params))

        subfn = cmd.MemoryControl.Subfunction(request.subfn)
        if subfn == cmd.MemoryControl.Subfunction.Write:
            self.logger.error('Failed to get a response for WriteMemory request.')
        elif subfn == cmd.MemoryControl.Subfunction.WriteRPV:
            self.logger.error('Failed to get a response for WriteRPV request.')
        else:
            self.logger.critical('Got a response for a request we did not send. Not supposed to happen!')

        if self.target_update_request_being_processed is not None:
            self.target_update_request_being_processed.complete(success=False)

        self.completed()

    def completed(self) -> None:
        """Common code after success and failure callbacks"""
        self.request_pending = False
        self.entry_being_updated = None
        self.request_of_entry_being_updated = None
        self.target_update_request_being_processed = None
        self.target_update_value_written = None
