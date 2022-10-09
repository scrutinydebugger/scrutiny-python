#    memory_reader.py
#        Synchronize the datastore with the device
#        Poll for entries that are watched and update the datastore with data read from the
#        device.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import logging
import copy
import traceback
import enum
from sortedcontainers import SortedSet  # type: ignore

from scrutiny.server.protocol import *
import scrutiny.server.protocol.commands as cmd
import scrutiny.server.protocol.typing as protocol_typing
from scrutiny.server.device.request_dispatcher import RequestDispatcher, SuccessCallback, FailureCallback
from scrutiny.server.datastore.datastore import Datastore, WatchCallback
from scrutiny.server.datastore.datastore_entry import *
from scrutiny.core.memory_content import MemoryContent, Cluster

from typing import Any, List, Tuple, Optional, cast, Set, Dict


class DataStoreEntrySortableByAddress:
    """Wrapper around a DatastoreVariableEntry that can sort them by their address.
    Used to feed a SortedSet"""
    entry: DatastoreVariableEntry

    def __init__(self, entry: DatastoreVariableEntry):
        self.entry = entry

    def __hash__(self):
        return self.entry.__hash__()  # For hash uniqueness

    def __eq__(self, other):
        return self.entry.get_address() == other.entry.get_address()

    def __ne__(self, other):
        return self.entry.get_address() != other.entry.get_address()

    def __lt__(self, other):
        return self.entry.get_address() < other.entry.get_address()

    def __le__(self, other):
        return self.entry.get_address() <= other.entry.get_address()

    def __gt__(self, other):
        return self.entry.get_address() > other.entry.get_address()

    def __ge__(self, other):
        return self.entry.get_address() >= other.entry.get_address()


class DataStoreEntrySortableByRpvId:
    """Wrapper around DatastoreRPVEntry that can be sorted by RPV ID. 
    Used to feed a SortedSet"""
    entry: DatastoreRPVEntry

    def __init__(self, entry: DatastoreRPVEntry):
        self.entry = entry

    def __hash__(self):
        return self.entry.__hash__()  # For hash uniqueness

    def __eq__(self, other):
        return self.entry.get_rpv().id == other.entry.get_rpv().id

    def __ne__(self, other):
        return self.entry.get_rpv().id != other.entry.get_rpv().id

    def __lt__(self, other):
        return self.entry.get_rpv().id < other.entry.get_rpv().id

    def __le__(self, other):
        return self.entry.get_rpv().id <= other.entry.get_rpv().id

    def __gt__(self, other):
        return self.entry.get_rpv().id > other.entry.get_rpv().id

    def __ge__(self, other):
        return self.entry.get_rpv().id >= other.entry.get_rpv().id


class ReadType(enum.Enum):
    """Type of read request. Memory and RPV reads uses a different protocol commands"""
    MemoryBlock = enum.auto()
    RuntimePublishedValues = enum.auto()


class MemoryReader:
    """Class that poll the device for its memory content and update the datastore
    with new values when the content is received.
    It treats Variable and RuntimePublishedValues differently as they use a different protocol command.

    The Memory reader only polls for entry with a least 1 watcher
    """

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
    watched_var_entries_sorted_by_address: SortedSet    # Set of entries referring variables sorted by address
    watched_rpv_entries_sorted_by_id: SortedSet         # Set of entries referring RuntimePublishedValues (RPV) sorted by ID
    memory_read_cursor: int     # Cursor used for round-robin inside the SortedSet of Variables datastore entries
    rpv_read_cursor: int        # Cursor used for round-robin inside the SortedSet of RPV datastore entries
    entries_in_pending_read_mem_request: List[DatastoreVariableEntry]   # List of memory entries in the request we're waiting for
    # List of RPV entries in the request we're waiting for. Stored in a dict with their ID as key
    entries_in_pending_read_rpv_request: Dict[int, DatastoreRPVEntry]
    actual_read_type: ReadType  # Tell wether we are doing RPV read or memory read request. We alternate from one another.

    def __init__(self, protocol: Protocol, dispatcher: RequestDispatcher, datastore: Datastore, request_priority: int):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dispatcher = dispatcher
        self.protocol = protocol
        self.datastore = datastore
        self.request_priority = request_priority
        self.datastore.add_watch_callback(WatchCallback(self.the_watch_callback))
        self.datastore.add_unwatch_callback(WatchCallback(self.the_unwatch_callback))

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
        self.forbidden_regions.append((start_addr, size))

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
        self.stop_requested = True

    def reset(self) -> None:
        """Put back the memory reader to its startup state"""
        self.stop_requested = False
        self.request_pending = False
        self.started = False
        self.actual_read_type = ReadType.MemoryBlock    # Alternate between RPV and Mem

        self.max_request_payload_size = self.DEFAULT_MAX_REQUEST_PAYLOAD_SIZE
        self.max_response_payload_size = self.DEFAULT_MAX_RESPONSE_PAYLOAD_SIZE
        self.forbidden_regions = []
        self.readonly_regions = []

        self.watched_var_entries_sorted_by_address = SortedSet()
        self.watched_rpv_entries_sorted_by_id = SortedSet()
        self.memory_read_cursor = 0
        self.rpv_read_cursor = 0
        self.entries_in_pending_read_mem_request = []
        self.entries_in_pending_read_rpv_request = {}

    def process(self) -> None:
        """To be called periodically"""
        if not self.started:
            self.reset()
            return
        elif self.stop_requested and not self.request_pending:
            self.reset()
            return

        read_type_considered: Set[ReadType] = set()
        while not self.request_pending and len(read_type_considered) < 2:    # 2 = len(RPV, Memblock)
            read_type_considered.add(self.actual_read_type)

            # We want to read everything in a round robin scheme. But we need to read memory and RPV as much without discrimination
            # So we need to do   ReadMem1, ReadMem2, ReadMem3, ReadRPV1, ReadRPV2  **WRAP**  ReadMem1, ReadMem2, etc

            if self.actual_read_type == ReadType.MemoryBlock:
                request, var_entries_in_request, wrapped_to_beginning = self.make_next_read_memory_request()
                if request is not None:
                    self.logger.debug('Registering a MemoryRead request for %d datastore entries. %s' % (len(var_entries_in_request), request))
                    self.dispatch(request)
                    self.entries_in_pending_read_var_request = var_entries_in_request

                # if there's nothing to send or that we completed one round
                if wrapped_to_beginning or self.request_pending == False:
                    self.actual_read_type = ReadType.RuntimePublishedValues  # Next type

            elif self.actual_read_type == ReadType.RuntimePublishedValues:
                request, rpv_entries_in_request, wrapped_to_beginning = self.make_next_read_rpv_request()
                if request is not None:
                    self.logger.debug('Registering a ReadRPV request for %d datastore entries. %s' % (len(rpv_entries_in_request), request))
                    self.dispatch(request)
                    self.entries_in_pending_read_rpv_request = {}
                    for entry in rpv_entries_in_request:
                        self.entries_in_pending_read_rpv_request[entry.get_rpv().id] = entry

                if wrapped_to_beginning or self.request_pending == False:
                    self.actual_read_type = ReadType.MemoryBlock  # Next type
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
        self.request_pending = True

    def make_next_read_memory_request(self) -> Tuple[Optional[Request], List[DatastoreVariableEntry], bool]:
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
            for region in self.forbidden_regions:
                region_start = region[0]
                region_end = region_start + region[1] - 1
                entry_start = candidate_entry.get_address()
                entry_end = entry_start + candidate_entry.get_size() - 1

                if not (entry_end < region_start or entry_start > region_end):
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

    def success_callback(self, request: Request, response: Response, params: Any = None) -> None:
        """Called when a request completes and succeeds"""
        self.logger.debug("Success callback. Response=%s, Params=%s" % (response, params))
        subfn = cmd.MemoryControl.Subfunction(response.subfn)
        if subfn == cmd.MemoryControl.Subfunction.Read:
            self.success_callback_memory_read(request, response, params)
        elif subfn == cmd.MemoryControl.Subfunction.ReadRPV:
            self.success_callback_rpv_read(request, response, params)
        else:
            self.logger.critical('Got a response for a request we did not send. Not supposed to happen!')

        self.read_completed()

    def success_callback_memory_read(self, request: Request, response: Response, params: Any = None) -> None:
        """Called when a MemoryRead request completes and succeeds"""
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
                except Exception as e:
                    self.logger.critical('Error while writing datastore. %s' % str(e))
                    self.logger.debug(traceback.format_exc())
            except:
                self.logger.error('Response for ReadMemory read request is malformed and must be discared.')
                self.logger.debug(traceback.format_exc())
        else:
            self.logger.warning('Response for ReadMemory has been refused with response code %s.' % response.code)

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
            except:
                self.logger.error('Response for ReadRPV read request is malformed and must be discared.')
                self.logger.debug(traceback.format_exc())
        else:
            self.logger.warning('Response for ReadRPV has been refused with response code %s.' % response.code)

    def failure_callback(self, request: Request, params: Any = None) -> None:
        """Callback called by the request dispatcher when a request fails to complete"""
        self.logger.debug("Failure callback. Request=%s. Params=%s" % (request, params))
        subfn = cmd.MemoryControl.Subfunction(request.subfn)
        if subfn == cmd.MemoryControl.Subfunction.Read:
            self.logger.error('Failed to get a response for ReadMemory request.')
        elif subfn == cmd.MemoryControl.Subfunction.ReadRPV:
            self.logger.error('Failed to get a response for ReadRPV request.')
        else:
            self.logger.critical('Got a response for a request we did not send. Not supposed to happen!')

        self.read_completed()

    def read_completed(self) -> None:
        """Common code after success and failure callbacks"""
        self.request_pending = False
