#    memory_writer.py
#        Synchronize the datastore with the device
#        Poll for entries that are watched and update the device with value change request
#        coming from the user in the datastore.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import logging
from scrutiny.server.datastore.datastore_entry import DatastoreRPVEntry, DatastoreVariableEntry, UpdateTargetRequest

from scrutiny.server.protocol import *
import scrutiny.server.protocol.commands as cmd
import scrutiny.server.protocol.typing as protocol_typing
from scrutiny.server.device.request_dispatcher import RequestDispatcher, SuccessCallback, FailureCallback
from scrutiny.server.datastore.datastore import Datastore
from scrutiny.server.datastore.datastore_entry import DatastoreEntry
from scrutiny.core.codecs import Codecs, Encodable
from scrutiny.core.typehints import GenericCallback
from scrutiny.core.basic_types import MemoryRegion
import time
import queue
from typing import Any, List, Optional, cast, Callable


class RawMemoryWriteRequestCompletionCallback(GenericCallback):
    callback: Callable[["RawMemoryWriteRequest", bool, str], None]


class RawMemoryWriteRequest:
    address: int
    data: bytes
    completed: bool
    success: bool
    completion_callback: Optional[RawMemoryWriteRequestCompletionCallback]
    completion_timestamp: Optional[float]

    def __init__(self, address: int, data: bytes, callback: Optional[RawMemoryWriteRequestCompletionCallback] = None):
        self.address = address
        self.data = data
        self.completed = False
        self.success = False
        self.completion_callback = callback
        self.completion_timestamp = None

    def set_completed(self, success: bool, failure_reason: str = "") -> None:
        self.completed = True
        self.success = success
        self.completion_timestamp = time.time()
        if self.completion_callback is not None:
            self.completion_callback(self, success, failure_reason)


class MemoryWriter:

    DEFAULT_MAX_REQUEST_PAYLOAD_SIZE: int = 1024
    DEFAULT_MAX_RESPONSE_PAYLOAD_SIZE: int = 1024

    logger: logging.Logger
    dispatcher: RequestDispatcher       # We put the request in here, and we know they'll go out
    protocol: Protocol                  # The actual protocol. Used to build the request payloads
    request_priority: int               # Our dispatcher priority
    datastore: Datastore    # The datastore the look for entries to update
    stop_requested: bool    # Requested to stop polling
    pending_request: Optional[Request]   # The request presently being sent
    started: bool           # Indicate if enabled or not
    max_request_payload_size: int   # Maximum size for a request payload gotten from the InfoPoller
    max_response_payload_size: int  # Maximum size for a response payload gotten from the InfoPoller
    forbidden_regions: List[MemoryRegion]    # List of memory regions to avoid. Gotten from InfoPoller
    readonly_regions: List[MemoryRegion]     # List of memory region that can only be read. Gotten from InfoPoller
    memory_write_allowed: bool  # Indicates if writing to memory is allowed.

    entry_being_updated: Optional[DatastoreEntry]   # The datastore entry updated by the actual pending request. None if no request is pending
    # Update request attached to the entry being updated. It's what'S coming from the API
    target_update_request_being_processed: Optional[UpdateTargetRequest]
    target_update_value_written: Optional[Encodable]

    raw_write_request_queue: "queue.Queue[RawMemoryWriteRequest]"
    active_raw_write_request: Optional[RawMemoryWriteRequest]
    active_raw_write_request_remaining_data: Optional[bytes]

    def __init__(self, protocol: Protocol, dispatcher: RequestDispatcher, datastore: Datastore, request_priority: int):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dispatcher = dispatcher
        self.protocol = protocol
        self.datastore = datastore
        self.request_priority = request_priority

        self.raw_write_request_queue = queue.Queue()
        self.active_raw_write_request = None
        self.target_update_request_being_processed = None

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
            self.forbidden_regions.append(MemoryRegion(start=start_addr, size=size))
        else:
            self.logger.warning('Adding a forbidden region with non-positive size %d' % size)

    def add_readonly_region(self, start_addr: int, size: int) -> None:
        """Add a memory region that can only be read. We will avoid any write to them. 
        They normally are broadcasted by the device itself"""
        if size > 0:
            self.readonly_regions.append(MemoryRegion(start=start_addr, size=size))
        else:
            self.logger.warning('Adding a read only region with non-positive size %d' % size)

    def request_memory_write(self, address: int, data: bytes, callback: Optional[RawMemoryWriteRequestCompletionCallback] = None) -> RawMemoryWriteRequest:
        """Request the reader to write an arbitrary memory region with a callback to be called upon completion"""
        request = RawMemoryWriteRequest(
            address=address,
            data=data,
            callback=callback
        )
        self.raw_write_request_queue.put(request)
        return request

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
        self.pending_request = None
        self.started = False

        # Clear all pending request and inform the external world that they failed.
        if self.active_raw_write_request is not None:
            self.active_raw_write_request.set_completed(False, "Stopping communication with device")

        while not self.raw_write_request_queue.empty():
            self.raw_write_request_queue.get().set_completed(False, "Stopping communication with device")

        if self.target_update_request_being_processed is not None:
            self.target_update_request_being_processed.complete(False)

        self.clear_active_entry_write_request()
        self.clear_active_raw_write_request()

    def clear_config(self) -> None:
        """Erase the configuration coming from the device handler"""
        self.max_request_payload_size = self.DEFAULT_MAX_REQUEST_PAYLOAD_SIZE
        self.max_response_payload_size = self.DEFAULT_MAX_RESPONSE_PAYLOAD_SIZE
        self.forbidden_regions = []
        self.readonly_regions = []
        self.memory_write_allowed = True

    def allow_memory_write(self, val: bool) -> None:
        self.memory_write_allowed = val

    def clear_active_raw_write_request(self) -> None:
        self.active_raw_write_request = None
        self.active_raw_write_request_remaining_data = None

    def clear_active_entry_write_request(self) -> None:
        self.entry_being_updated = None
        self.target_update_request_being_processed = None
        self.target_update_value_written = None

    def reset(self) -> None:
        """Put back the memory writer to its startup state"""
        self.set_standby()
        self.clear_config()

    def process(self) -> None:
        """To be called periodically"""
        if not self.started:
            self.set_standby()
            return
        elif self.stop_requested and not self.pending_request:
            self.set_standby()
            return

        if not self.pending_request:
            # We give priority to raw write request. Maybe both type of request should use the same queue to solve the priority question?
            request: Optional[Request] = None
            if self.active_raw_write_request is not None or not self.raw_write_request_queue.empty():
                assert self.entry_being_updated is None
                request = self.make_next_raw_memory_write_request()
            elif self.entry_being_updated is not None or self.datastore.has_pending_target_update():
                assert self.active_raw_write_request is None
                request = self.make_next_entry_write_request()

            if request is not None:
                self.dispatch(request)

    def make_next_raw_memory_write_request(self) -> Optional[Request]:
        """Writes a memory block in the device based on a write request tied to no datastore entry. Just a raw write (coming from the API)"""
        request: Optional[Request] = None

        while self.active_raw_write_request is None:
            if self.raw_write_request_queue.empty():
                break
            self.clear_active_raw_write_request()
            self.active_raw_write_request = self.raw_write_request_queue.get()

            is_in_forbidden_region = False
            is_in_readonly_region = False
            candidate_region = MemoryRegion(start=self.active_raw_write_request.address, size=len(self.active_raw_write_request.data))
            for readonly_region in self.readonly_regions:
                if candidate_region.touches(readonly_region):
                    is_in_readonly_region = True
                    break
            for forbidden_region in self.forbidden_regions:
                if candidate_region.touches(forbidden_region):
                    is_in_forbidden_region = True
                    break

            if is_in_forbidden_region:
                self.active_raw_write_request.set_completed(False, "Forbidden")
                self.clear_active_raw_write_request()
            elif is_in_readonly_region:
                self.active_raw_write_request.set_completed(False, "Read only")
                self.clear_active_raw_write_request()
            else:
                self.active_raw_write_request_remaining_data = self.active_raw_write_request.data   # bytes are immutable. Makes a copy

        if self.active_raw_write_request is not None:
            assert self.active_raw_write_request_remaining_data is not None
            cursor = len(self.active_raw_write_request.data) - len(self.active_raw_write_request_remaining_data)
            n_to_write = min(self.max_request_payload_size, len(self.active_raw_write_request_remaining_data))
            block = (self.active_raw_write_request.address + cursor, self.active_raw_write_request_remaining_data[:n_to_write])
            self.active_raw_write_request_remaining_data = self.active_raw_write_request_remaining_data[n_to_write:]
            request = self.protocol.write_memory_blocks([block])

        return request

    def make_next_entry_write_request(self) -> Optional[Request]:
        """
        This method generate a write request by moving in a list of watched variable entries
        It works in a round-robin scheme and will send write request 1 by 1, without agglomeration.
        It considers device internal max buffer size
        """
        request: Optional[Request] = None

        if self.entry_being_updated is None:
            while True:
                update_request = self.datastore.pop_target_update_request()

                if update_request is None:
                    break
                # Make sure we have the right to write to that memory region. Fails right away if we don't
                allowed = True
                if isinstance(update_request.entry, DatastoreVariableEntry):
                    assert update_request.entry.__class__ != DatastoreEntry  # for mypy
                    allowed = self.memory_write_allowed
                    address = update_request.entry.get_address()
                    # We don't check for bitfield size because the device will access the whole word anyway
                    size = update_request.entry.get_data_type().get_size_byte()
                    candidate_region = MemoryRegion(start=address, size=size)
                    for readonly_region in self.readonly_regions:
                        if candidate_region.touches(readonly_region):
                            allowed = False
                            break
                    for forbidden_region in self.forbidden_regions:
                        if candidate_region.touches(forbidden_region):
                            allowed = False
                            break

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
                    except Exception:
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
                    except Exception:
                        encoding_succeeded = False
                    if encoding_succeeded:
                        self.target_update_value_written = value_to_write
                        request = self.protocol.write_runtime_published_values((rpv.id, value_to_write))
                    else:
                        self.target_update_request_being_processed.complete(success=False)
                else:
                    raise RuntimeError('entry_being_updated should be of type %s' % self.entry_being_updated.__class__.__name__)

        return request

    def success_callback(self, request: Request, response: Response, params: Any = None) -> None:
        """Called when a request completes and succeeds"""
        self.logger.debug("Success callback. Response=%s, Params=%s" % (response, params))
        assert request == self.pending_request, "Processing a request that we are not supposed to. This should not happen"

        subfn = cmd.MemoryControl.Subfunction(response.subfn)
        if subfn == cmd.MemoryControl.Subfunction.Write or subfn == cmd.MemoryControl.Subfunction.WriteMasked:
            if self.entry_being_updated is not None:
                self.success_callback_var_write(request, response, params)
            elif self.active_raw_write_request is not None:
                self.success_callback_raw_memory_write(request, response, params)
            else:
                self.logger.warning("Received a WriteMemory response but none was expected")
        elif subfn == cmd.MemoryControl.Subfunction.WriteRPV:
            if self.entry_being_updated is not None:
                self.success_callback_rpv_write(request, response, params)
            else:
                self.logger.warning("Received a WriteRPV response but none was expected")
        else:
            self.logger.critical('Got a response for a request we did not send. Not supposed to happen!')

        self.completed()

    def success_callback_var_write(self, request: Request, response: Response, params: Any = None) -> None:
        """Called when a memory write request completes and succeeds"""
        assert self.entry_being_updated is not None
        assert self.target_update_request_being_processed is not None

        if response.code == ResponseCode.OK:
            request_data = cast(protocol_typing.Request.MemoryControl.Write, self.protocol.parse_request(request))
            response_data = cast(protocol_typing.Response.MemoryControl.Write, self.protocol.parse_response(response))

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
            self.logger.warning('Response for WriteMemory has been refused with response code %s.' % response.code)
            self.target_update_request_being_processed.complete(False)

        self.clear_active_entry_write_request()

    def success_callback_raw_memory_write(self, request: Request, response: Response, params: Any = None) -> None:
        assert self.active_raw_write_request is not None
        assert self.active_raw_write_request_remaining_data is not None

        if response.code == ResponseCode.OK:
            request_data = cast(protocol_typing.Request.MemoryControl.Write, self.protocol.parse_request(request))
            response_data = cast(protocol_typing.Response.MemoryControl.Write, self.protocol.parse_response(response))

            response_match_request = True
            if len(request_data['blocks_to_write']) != 1 or len(response_data['written_blocks']) != 1:
                response_match_request = False
            else:
                if request_data['blocks_to_write'][0]['address'] != response_data['written_blocks'][0]['address']:
                    response_match_request = False

                if len(request_data['blocks_to_write'][0]['data']) != response_data['written_blocks'][0]['length']:
                    response_match_request = False

            if response_match_request:
                if len(self.active_raw_write_request_remaining_data) == 0:
                    self.active_raw_write_request.set_completed(success=True)
                    self.clear_active_raw_write_request()
                else:
                    pass  # Do nothing. More data to write for that request.
            else:
                self.active_raw_write_request.set_completed(success=False, failure_reason="Communication error")
                self.clear_active_raw_write_request()
                self.logger.error('Received a WriteMemory response that does not match the request')
        else:
            self.logger.warning('Response for WriteMemory has been refused with response code %s.' % response.code)
            self.active_raw_write_request.set_completed(success=False, failure_reason="Refused by the device")
            self.clear_active_raw_write_request()

    def success_callback_rpv_write(self, request: Request, response: Response, params: Any = None) -> None:
        """Called when a RPV write request completes and succeeds"""
        assert self.entry_being_updated is not None
        assert self.target_update_request_being_processed is not None

        if response.code == ResponseCode.OK:
            request_data = cast(protocol_typing.Request.MemoryControl.WriteRPV, self.protocol.parse_request(request))
            response_data = cast(protocol_typing.Response.MemoryControl.WriteRPV, self.protocol.parse_response(response))

            response_match_request = True
            if len(request_data['rpvs']) != 1 or len(response_data['written_rpv']) != 1:
                response_match_request = False
            else:
                if request_data['rpvs'][0]['id'] != response_data['written_rpv'][0]['id']:
                    response_match_request = False

            if response_match_request:
                self.entry_being_updated.set_value(self.target_update_value_written)
                self.target_update_request_being_processed.complete(success=True)
            else:
                self.target_update_request_being_processed.complete(success=False)
                self.logger.error('Received a WriteRPV response that does not match the request')
        else:
            self.logger.warning('Response for WriteRPV has been refused with response code %s.' % response.code)
            self.target_update_request_being_processed.complete(success=False)

        self.clear_active_entry_write_request()

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
            self.clear_active_entry_write_request()

        if self.active_raw_write_request is not None:
            self.active_raw_write_request.set_completed(False, "Request failed")
            self.clear_active_raw_write_request()

        self.completed()

    def completed(self) -> None:
        """Common code after success and failure callbacks"""
        self.pending_request = None

    def dispatch(self, request: Request) -> None:
        """Sends a request to the request dispatcher and assign the corrects completion callbacks"""
        self.logger.debug('Registering a MemoryWrite request. %s' % (request))
        self.dispatcher.register_request(
            request=request,
            success_callback=SuccessCallback(self.success_callback),
            failure_callback=FailureCallback(self.failure_callback),
            priority=self.request_priority
        )
        self.pending_request = request
