#    memory_reader.py
#        Synchronize the datastore with the device
#        Poll for entries that are watched and update the datastore with data read from the
#        device.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import logging
import copy
import traceback
import enum
import time
import queue
from sortedcontainers import SortedSet  # type: ignore

from scrutiny.server.protocol import *
import scrutiny.server.protocol.commands as cmd
import scrutiny.server.protocol.typing as protocol_typing
from scrutiny.server.device.request_dispatcher import RequestDispatcher, SuccessCallback, FailureCallback
from scrutiny.server.datastore.datastore import Datastore, WatchCallback
from scrutiny.server.datastore.datastore_entry import *
from scrutiny.core.memory_content import MemoryContent, Cluster
from scrutiny.core.basic_types import MemoryRegion

from typing import cast, Set, List, Any, Optional, Callable, Tuple, Dict
from scrutiny.core.typehints import GenericCallback


class RawMemoryReadRequestCompletionCallback(GenericCallback):
    callback: Callable[["RawMemoryReadRequest", bool, Optional[bytes], str], None]


class RawMemoryReadRequest:
    address: int
    size: int
    completed: bool
    success: bool
    completion_callback: Optional[RawMemoryReadRequestCompletionCallback]
    completion_timestamp: Optional[float]

    def __init__(self, address: int, size: int, callback: Optional[RawMemoryReadRequestCompletionCallback] = None) -> None:
        self.address = address
        self.size = size
        self.completed = False
        self.success = False
        self.completion_callback = callback
        self.completion_timestamp = None

    def set_completed(self, success: bool, data: Optional[bytes], failure_reason: str = "") -> None:
        self.completed = True
        self.success = success
        self.completion_timestamp = time.time()
        if self.completion_callback is not None:
            self.completion_callback(self, success, data, failure_reason)


class DataStoreEntrySortableByAddress:
    """Wrapper around a DatastoreVariableEntry that can sort them by their address.
    Used to feed a SortedSet"""
    entry: DatastoreVariableEntry

    def __init__(self, entry: DatastoreVariableEntry):
        self.entry = entry

    def __hash__(self) -> int:
        return self.entry.__hash__()  # For hash uniqueness

    def __eq__(self, other: object) -> bool:
        if isinstance(other, self.__class__):
            return self.entry.get_address() == other.entry.get_address()
        return False

    def __ne__(self, other: object) -> bool:
        if isinstance(other, self.__class__):
            return self.entry.get_address() != other.entry.get_address()
        return False

    def __lt__(self, other: "DataStoreEntrySortableByAddress") -> bool:
        return self.entry.get_address() < other.entry.get_address()

    def __le__(self, other: "DataStoreEntrySortableByAddress") -> bool:
        return self.entry.get_address() <= other.entry.get_address()

    def __gt__(self, other: "DataStoreEntrySortableByAddress") -> bool:
        return self.entry.get_address() > other.entry.get_address()

    def __ge__(self, other: "DataStoreEntrySortableByAddress") -> bool:
        return self.entry.get_address() >= other.entry.get_address()


class DataStoreEntrySortableByRpvId:
    """Wrapper around DatastoreRPVEntry that can be sorted by RPV ID. 
    Used to feed a SortedSet"""
    entry: DatastoreRPVEntry

    def __init__(self, entry: DatastoreRPVEntry) -> None:
        self.entry = entry

    def __hash__(self) -> int:
        return self.entry.__hash__()  # For hash uniqueness

    def __eq__(self, other: object) -> bool:
        if isinstance(other, self.__class__):
            return self.entry.get_rpv().id == other.entry.get_rpv().id
        return False

    def __ne__(self, other: object) -> bool:
        if isinstance(other, self.__class__):
            return self.entry.get_rpv().id != other.entry.get_rpv().id
        return False

    def __lt__(self, other: "DataStoreEntrySortableByRpvId") -> bool:
        return self.entry.get_rpv().id < other.entry.get_rpv().id

    def __le__(self, other: "DataStoreEntrySortableByRpvId") -> bool:
        return self.entry.get_rpv().id <= other.entry.get_rpv().id

    def __gt__(self, other: "DataStoreEntrySortableByRpvId") -> bool:
        return self.entry.get_rpv().id > other.entry.get_rpv().id

    def __ge__(self, other: "DataStoreEntrySortableByRpvId") -> bool:
        return self.entry.get_rpv().id >= other.entry.get_rpv().id


class ReadType(enum.Enum):
    """Type of read request. Memory and RPV reads uses a different protocol commands"""
    Variable = enum.auto()
    RuntimePublishedValues = enum.auto()
    RawMemRead = enum.auto()


class MemoryReader:
    """Class that poll the device for its memory content and update the datastore
    with new values when the content is received.
    It treats Variable and RuntimePublishedValues differently as they use a different protocol command.

    The Memory reader only polls for entry with a least 1 watcher
    """

    DEFAULT_MAX_REQUEST_PAYLOAD_SIZE: int = 1024
    DEFAULT_MAX_RESPONSE_PAYLOAD_SIZE: int = 1024
    MAX_RAW_READ_SIZE = 2**14 - 1

    logger: logging.Logger
    dispatcher: RequestDispatcher       # We put the request in here, and we know they'll go out
    protocol: Protocol                  # The actual protocol. Used to build the request payloads
    request_priority: int               # Our dispatcher priority
    datastore: Datastore    # The datastore the look for entries to update
    stop_requested: bool    # Requested to stop polling
    pending_request: Optional[Request]   # Contains the request being waited on. None if there is none
    started: bool           # Indicate if enabled or not
    max_request_payload_size: int   # Maximum size for a request payload gotten from the InfoPoller
    max_response_payload_size: int  # Maximum size for a response payload gotten from the InfoPoller
    forbidden_regions: List[MemoryRegion]    # List of memory regions to avoid. Gotten from InfoPoller
    watched_var_entries_sorted_by_address: SortedSet    # Set of entries referring variables sorted by address
    watched_rpv_entries_sorted_by_id: SortedSet         # Set of entries referring RuntimePublishedValues (RPV) sorted by ID
    memory_read_cursor: int     # Cursor used for round-robin inside the SortedSet of Variables datastore entries
    rpv_read_cursor: int        # Cursor used for round-robin inside the SortedSet of RPV datastore entries
    entries_in_pending_read_var_request: List[DatastoreVariableEntry]   # List of memory entries in the request we're waiting for
    # List of RPV entries in the request we're waiting for. Stored in a dict with their ID as key
    entries_in_pending_read_rpv_request: Dict[int, DatastoreRPVEntry]
    actual_read_type: ReadType  # Tell wether we are doing RPV read or memory read request. We alternate from one another.
    raw_read_request_queue: "queue.Queue[RawMemoryReadRequest]"
    active_raw_read_request: Optional[RawMemoryReadRequest]
    active_raw_read_request_cursor: int
    active_raw_read_request_data: bytes

    def __init__(self, protocol: Protocol, dispatcher: RequestDispatcher, datastore: Datastore, request_priority: int):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dispatcher = dispatcher
        self.protocol = protocol
        self.datastore = datastore
        self.request_priority = request_priority
        self.datastore.add_watch_callback(WatchCallback(self.the_watch_callback))
        self.datastore.add_unwatch_callback(WatchCallback(self.the_unwatch_callback))
        self.active_raw_read_request = None
        self.raw_read_request_queue = queue.Queue()

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
        if start_addr >= 0 and size > 0:
            self.forbidden_regions.append(MemoryRegion(start=start_addr, size=size))

    def request_memory_read(self, address: int, size: int, callback: Optional[RawMemoryReadRequestCompletionCallback] = None) -> RawMemoryReadRequest:
        """Request the reader to read an arbitrary memory region with a callback to be called upon completion"""
        request = RawMemoryReadRequest(
            address=address,
            size=size,
            callback=callback
        )
        self.raw_read_request_queue.put(request)
        return request

    def the_watch_callback(self, entry_id: str) -> None:
        """Callback called by the datastore whenever somebody starts watching an entry."""
        entry = self.datastore.get_entry(entry_id)
        if isinstance(entry, DatastoreVariableEntry):
            # Memory reader reads by address. Only Variables has that
            self.watched_var_entries_sorted_by_address.add(DataStoreEntrySortableByAddress(entry))
        elif isinstance(entry, DatastoreRPVEntry):
            self.watched_rpv_entries_sorted_by_id.add(DataStoreEntrySortableByRpvId(entry))

    def the_unwatch_callback(self, entry_id: str) -> None:
        """Callback called by the datastore  whenever somebody stops watching an entry"""
        if len(self.datastore.get_watchers(entry_id)) == 0:
            entry = self.datastore.get_entry(entry_id)
            if isinstance(entry, DatastoreVariableEntry):
                self.watched_var_entries_sorted_by_address.discard(DataStoreEntrySortableByAddress(entry))
            elif isinstance(entry, DatastoreRPVEntry):
                self.watched_rpv_entries_sorted_by_id.discard(DataStoreEntrySortableByRpvId(entry))

    def start(self) -> None:
        """Enable the memory reader to poll the devices"""
        self.started = True

    def stop(self) -> None:
        """Stops the memory readers from polling the device"""
        self.logger.debug('Stop requested')
        self.stop_requested = True

    def fully_stopped(self) -> bool:
        return self.started == False and self.stop_requested == False

    def clear_active_raw_read_request(self) -> None:
        self.active_raw_read_request = None
        self.active_raw_read_request_data = bytes()
        self.active_raw_read_request_cursor = 0

    def reset(self) -> None:
        """Put back the memory reader to its startup state"""
        self.set_standby()
        self.clear_config()

    def set_standby(self) -> None:
        """Put the state machine into standby and clear all internal buffers so that the logic restarts from the beginning"""
        self.stop_requested = False
        self.pending_request = None
        self.started = False
        self.actual_read_type = ReadType.Variable    # Alternate between RPV and Mem

        self.watched_var_entries_sorted_by_address = SortedSet()
        self.watched_rpv_entries_sorted_by_id = SortedSet()
        self.memory_read_cursor = 0
        self.rpv_read_cursor = 0
        self.entries_in_pending_read_var_request = []
        self.entries_in_pending_read_rpv_request = {}

        if self.active_raw_read_request is not None:
            self.active_raw_read_request.set_completed(False, None, "Stopping communication with device")

        while not self.raw_read_request_queue.empty():
            self.raw_read_request_queue.get().set_completed(False, None, "Stopping communication with device")

        self.clear_active_raw_read_request()

    def clear_config(self) -> None:
        """Erase the configuration coming from the device handler"""
        self.max_request_payload_size = self.DEFAULT_MAX_REQUEST_PAYLOAD_SIZE
        self.max_response_payload_size = self.DEFAULT_MAX_RESPONSE_PAYLOAD_SIZE
        self.forbidden_regions = []

    def process(self) -> None:
        """To be called periodically"""
        if not self.started:
            self.set_standby()
            return
        elif self.stop_requested and self.pending_request is None:
            self.set_standby()
            return

        read_type_considered: Set[ReadType] = set()
        while self.pending_request is None and len(read_type_considered) < len(ReadType):
            read_type_considered.add(self.actual_read_type)

            # We want to read everything in a round robin scheme. But we need to read memory and RPV as much without discrimination
            # So we need to do   ReadMem1, ReadMem2, ReadMem3, ReadRPV1, ReadRPV2  **WRAP**  ReadMem1, ReadMem2, etc

            if self.actual_read_type == ReadType.Variable:
                request, var_entries_in_request, wrapped_to_beginning = self.make_next_var_entries_request()
                if request is not None:
                    self.logger.debug('Registering a MemoryRead request for %d datastore entries. %s' % (len(var_entries_in_request), request))
                    self.dispatch(request)
                    self.entries_in_pending_read_var_request = var_entries_in_request

                # if there's nothing to send or that we completed one round
                if wrapped_to_beginning or self.pending_request is None:
                    self.actual_read_type = ReadType.RuntimePublishedValues

            elif self.actual_read_type == ReadType.RuntimePublishedValues:
                request, rpv_entries_in_request, wrapped_to_beginning = self.make_next_read_rpv_request()
                if request is not None:
                    self.logger.debug('Registering a ReadRPV request for %d datastore entries. %s' % (len(rpv_entries_in_request), request))
                    self.dispatch(request)
                    self.entries_in_pending_read_rpv_request = {}
                    for entry in rpv_entries_in_request:
                        self.entries_in_pending_read_rpv_request[entry.get_rpv().id] = entry

                if wrapped_to_beginning or self.pending_request is None:
                    self.actual_read_type = ReadType.RawMemRead

            elif self.actual_read_type == ReadType.RawMemRead:
                request, done = self.make_next_raw_mem_read_request()
                if request is not None:
                    self.logger.debug('Registering a MemoryRead request. %s' % (request))
                    self.dispatch(request)

                if done or self.pending_request is None:
                    self.actual_read_type = ReadType.Variable  # Next type

            else:
                raise Exception('Unknown read type.')

    def dispatch(self, request: Request) -> None:
        """Sends a request to the request dispatcher and assign the corrects completion callbacks"""
        self.dispatcher.register_request(
            request=request,
            success_callback=SuccessCallback(self.success_callback),
            failure_callback=FailureCallback(self.failure_callback),
            priority=self.request_priority
        )
        self.pending_request = request

    def make_next_var_entries_request(self) -> Tuple[Optional[Request], List[DatastoreVariableEntry], bool]:
        """
        This method generate a read request by moving in a list of watched variable entries
        It works in a round-robin scheme and will agglomerate entries that are contiguous in memory.
        Consider device internal max buffer size
        """
        cursor_wrapped = False
        max_block_per_request: int = self.max_request_payload_size // self.protocol.read_memory_request_size_per_block()
        entries_in_request: List[DatastoreVariableEntry] = []
        block_list: List[Tuple[int, int]] = []
        skipped_entries_count = 0
        clusters_in_request: List[Cluster] = []

        if self.memory_read_cursor >= len(self.watched_var_entries_sorted_by_address):
            self.memory_read_cursor = 0

        memory_to_read = MemoryContent(retain_data=False)  # We'll use that for agglomeration
        while len(entries_in_request) + skipped_entries_count < len(self.watched_var_entries_sorted_by_address):
            # .entry because we use a wrapper for SortedSet
            candidate_entry = cast(DatastoreVariableEntry, self.watched_var_entries_sorted_by_address[self.memory_read_cursor].entry)
            must_skip = False

            # Check for forbidden region. They disallow read and write
            is_in_forbidden_region = False
            candidate_region = MemoryRegion(start=candidate_entry.get_address(), size=candidate_entry.get_size())
            for forbidden_region in self.forbidden_regions:
                if candidate_region.touches(forbidden_region):
                    is_in_forbidden_region = True
                    break

            if is_in_forbidden_region:
                must_skip = True

            # Check if must skip
            if must_skip:
                skipped_entries_count += 1
            else:
                memory_to_read.add_empty(candidate_entry.get_address(), candidate_entry.get_size())
                clusters_candidate = memory_to_read.get_cluster_list_no_data_by_address()

                if len(clusters_candidate) > max_block_per_request:
                    break  # No space in request

                # Check response size limit
                response_payload_size = 0
                for cluster in clusters_candidate:
                    response_payload_size += self.protocol.read_memory_response_overhead_size_per_block()
                    response_payload_size += cluster.size

                if response_payload_size > self.max_response_payload_size:
                    break   # No space in response

                # We can fit the data so far..  latch the list of cluster and add the candidate to the entries to be updated
                clusters_in_request = copy.copy(clusters_candidate)
                entries_in_request.append(candidate_entry)   # Remember what entries is involved so we can update value once response is received

            self.memory_read_cursor += 1
            if self.memory_read_cursor >= len(self.watched_var_entries_sorted_by_address):
                self.memory_read_cursor = 0
                cursor_wrapped = True   # Indicates that we completed 1 round of round-robin for variables. Time to process RPVs

        block_list = []
        for cluster in clusters_in_request:
            block_list.append((cluster.start_addr, cluster.size))

        request = self.protocol.read_memory_blocks(block_list) if len(block_list) > 0 else None
        return (request, entries_in_request, cursor_wrapped)

    def make_next_read_rpv_request(self) -> Tuple[Optional[Request], List[DatastoreRPVEntry], bool]:
        """
        This method generate a read request by moving in a list of watched RPV entries
        It works in a round-robin scheme and will agglomerate entries until buffer size limit is reached
        """
        cursor_wrapped = False
        entries_in_request: List[DatastoreRPVEntry] = []
        if self.rpv_read_cursor >= len(self.watched_rpv_entries_sorted_by_id):
            self.rpv_read_cursor = 0

        while len(entries_in_request) < len(self.watched_rpv_entries_sorted_by_id):
            next_entry = cast(DatastoreRPVEntry, self.watched_rpv_entries_sorted_by_id[self.rpv_read_cursor].entry)

            candidate_list = entries_in_request + [next_entry]
            rpv_candidate_list = [x.get_rpv() for x in candidate_list]
            required_request_payload_size = self.protocol.read_rpv_request_required_size(rpv_candidate_list)
            required_response_payload_size = self.protocol.read_rpv_response_required_size(rpv_candidate_list)

            if required_request_payload_size > self.max_request_payload_size:
                break
            if required_response_payload_size > self.max_response_payload_size:
                break

            # We keep this entry.
            entries_in_request = candidate_list
            self.rpv_read_cursor += 1
            if self.rpv_read_cursor >= len(self.watched_rpv_entries_sorted_by_id):
                cursor_wrapped = True   # Indicates that we finished one round of round-robin for RPV entries. Times to check Variables
                self.rpv_read_cursor = 0

        ids = [x.get_rpv().id for x in entries_in_request]
        request = self.protocol.read_runtime_published_values(ids) if len(ids) > 0 else None
        return (request, entries_in_request, cursor_wrapped)

    def make_next_raw_mem_read_request(self) -> Tuple[Optional[Request], bool]:
        while self.active_raw_read_request is None:
            if self.raw_read_request_queue.empty():
                break
            self.clear_active_raw_read_request()
            self.active_raw_read_request = self.raw_read_request_queue.get()

            is_in_forbidden_region = False
            candidate_region = MemoryRegion(start=self.active_raw_read_request.address, size=self.active_raw_read_request.size)
            for forbidden_region in self.forbidden_regions:
                if candidate_region.touches(forbidden_region):
                    is_in_forbidden_region = True
                    break

            if self.active_raw_read_request.size > self.MAX_RAW_READ_SIZE:    # Hard limit
                self.active_raw_read_request.set_completed(False, None, "Size too big")
                self.clear_active_raw_read_request()
            elif self.active_raw_read_request.size < 0 or self.active_raw_read_request.address < 0:
                self.active_raw_read_request.set_completed(False, None, "Bad request")
                self.clear_active_raw_read_request()
            elif self.active_raw_read_request.address + self.active_raw_read_request.size >= 2**self.protocol.get_address_size_bits():
                self.active_raw_read_request.set_completed(False, None, "Read out of bound")
                self.clear_active_raw_read_request()
            elif is_in_forbidden_region:
                self.active_raw_read_request.set_completed(False, None, "Forbidden region")
                self.clear_active_raw_read_request()

        if self.active_raw_read_request is None:
            return None, True

        # We assume tha the device can accept a request with a single read block. Otherwise nothing would work.

        size = min(self.max_response_payload_size, self.active_raw_read_request.size - self.active_raw_read_request_cursor)
        address = self.active_raw_read_request.address + self.active_raw_read_request_cursor
        device_request = self.protocol.read_single_memory_block(address=address, length=size)
        self.active_raw_read_request_cursor += size
        last = self.active_raw_read_request_cursor >= self.active_raw_read_request.size

        return device_request, last

    def success_callback(self, request: Request, response: Response, params: Any = None) -> None:
        """Called when a request completes and succeeds"""
        self.logger.debug("Success callback. Response=%s, Params=%s" % (response, params))
        assert request == self.pending_request
        if request.command == cmd.MemoryControl:
            subfn = cmd.MemoryControl.Subfunction(response.subfn)
            if subfn == cmd.MemoryControl.Subfunction.Read:
                self.success_callback_memory_read(request, response, params)
            elif subfn == cmd.MemoryControl.Subfunction.ReadRPV:
                self.success_callback_rpv_read(request, response, params)
            else:
                self.logger.critical('Got a response for a request we did not send. Not supposed to happen!')
        else:
            self.logger.critical('Got a response for a request we did not send. Not supposed to happen!')

        self.read_completed()

    def success_callback_memory_read(self, request: Request, response: Response, params: Any = None) -> None:
        """Called when a MemoryRead request completes and succeeds"""
        if len(self.entries_in_pending_read_var_request) > 0:
            assert self.active_raw_read_request is None
            # Trigger by a readvar type
            if response.code == ResponseCode.OK:
                try:
                    response_data = cast(protocol_typing.Response.MemoryControl.Read, self.protocol.parse_response(response))
                    try:
                        temp_memory = MemoryContent()
                        for block in response_data['read_blocks']:
                            temp_memory.write(block['address'], block['data'])

                        for entry in self.entries_in_pending_read_var_request:
                            raw_data = temp_memory.read(entry.get_address(), entry.get_size())
                            entry.set_value_from_data(raw_data)
                            self.entries_in_pending_read_var_request = []
                    except Exception as e:
                        self.logger.critical('Error while writing datastore. %s' % str(e))
                        self.logger.debug(traceback.format_exc())
                except Exception:
                    self.logger.error('Response for ReadMemory read request is malformed and must be discarded.')
                    self.logger.debug(traceback.format_exc())
            else:
                self.logger.warning('Response for ReadMemory has been refused with response code %s.' % response.code)

        elif self.active_raw_read_request is not None:
            if response.code != ResponseCode.OK:
                self.active_raw_read_request.set_completed(False, None, failure_reason="Device refused the request")
                self.clear_active_raw_read_request()
            else:
                try:
                    request_data = cast(protocol_typing.Request.MemoryControl.Read, self.protocol.parse_request(request))
                    response_data = cast(protocol_typing.Response.MemoryControl.Read, self.protocol.parse_response(response))
                    assert len(response_data['read_blocks']) == 1, "Expected a single block in response"
                    assert len(request_data['blocks_to_read']) == 1, "Expected a single block in request"
                    address = response_data['read_blocks'][0]['address']
                    data = response_data['read_blocks'][0]['data']

                    assert address == request_data['blocks_to_read'][0]['address'], "Memory block does not match with request"
                    assert len(data) == request_data['blocks_to_read'][0]['length'], "Memory block does not match with request"
                    assert address + len(data) == self.active_raw_read_request.address + \
                        self.active_raw_read_request_cursor, "Memory block not the expected one"

                    self.active_raw_read_request_data += data

                    if len(self.active_raw_read_request_data) >= self.active_raw_read_request.size:
                        self.active_raw_read_request.set_completed(True, self.active_raw_read_request_data)
                        self.clear_active_raw_read_request()
                except Exception as e:
                    self.logger.error('Response for ReadMemory read request is malformed and must be discarded. ' + str(e))
                    self.logger.debug(traceback.format_exc())
                    self.active_raw_read_request.set_completed(False, None, failure_reason=str(e))
                    self.clear_active_raw_read_request()

    def success_callback_rpv_read(self, request: Request, response: Response, params: Any = None) -> None:
        """Called when a RPV read request completes and succeeds"""
        if response.code == ResponseCode.OK:
            try:
                response_data = cast(protocol_typing.Response.MemoryControl.ReadRPV, self.protocol.parse_response(response))
                try:
                    for read_rpv in response_data['read_rpv']:
                        if read_rpv['id'] not in self.entries_in_pending_read_rpv_request:
                            self.logger.error('Received data for RPV ID=0x%x but this Id was not requested' % (read_rpv['id']))
                        else:
                            entry = self.entries_in_pending_read_rpv_request[read_rpv['id']]
                            entry.set_value(read_rpv['data'])
                except Exception as e:
                    self.logger.critical('Error while writing datastore. %s' % str(e))
                    self.logger.debug(traceback.format_exc())
            except Exception:
                self.logger.error('Response for ReadRPV read request is malformed and must be discarded.')
                self.logger.debug(traceback.format_exc())
        else:
            self.logger.warning('Response for ReadRPV has been refused with response code %s.' % response.code)

    def failure_callback(self, request: Request, params: Any = None) -> None:
        """Callback called by the request dispatcher when a request fails to complete"""
        self.logger.debug("Failure callback. Request=%s. Params=%s" % (request, params))
        subfn = cmd.MemoryControl.Subfunction(request.subfn)
        if subfn == cmd.MemoryControl.Subfunction.Read:
            self.logger.error('Failed to get a response for ReadMemory request.')

            if self.active_raw_read_request is not None:
                self.active_raw_read_request.set_completed(False, None, failure_reason="Request did not get a response")
                self.clear_active_raw_read_request()

        elif subfn == cmd.MemoryControl.Subfunction.ReadRPV:
            self.logger.error('Failed to get a response for ReadRPV request.')
        else:
            self.logger.critical('Got a response for a request we did not send. Not supposed to happen!')

        self.read_completed()

    def read_completed(self) -> None:
        """Common code after success and failure callbacks"""
        self.pending_request = None
