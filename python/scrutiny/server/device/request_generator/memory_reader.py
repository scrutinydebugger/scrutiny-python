#    memory_reader.py
#        Synchronize the datastore with the device
#        Poll for entries that are watched.
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
from sortedcontainers import SortedSet # type: ignore

from scrutiny.server.protocol import *
from scrutiny.server.device.request_dispatcher import RequestDispatcher, SuccessCallback, FailureCallback
from scrutiny.server.datastore import Datastore, DatastoreEntry, WatchCallback
from scrutiny.core.memory_content import MemoryContent, Cluster

from typing import Any, List, Tuple, Optional


class DataStoreEntrySortableByAddress:
    entry:DatastoreEntry

    def __init__(self, entry):
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


class MemoryReader:

    DEFAULT_MAX_REQUEST_SIZE:int = 1024
    DEFAULT_MAX_RESPONSE_SIZE:int = 1024

    logger: logging.Logger
    dispatcher: RequestDispatcher
    protocol: Protocol
    datastore: Datastore
    read_priority: int
    write_priority: int
    stop_requested: bool
    read_request_pending: bool
    started: bool
    max_request_size:int
    max_response_size:int
    forbidden_regions:List[Tuple[int,int]]
    readonly_regions:List[Tuple[int,int]]
    watched_entries_sorted_by_address:SortedSet
    read_cursor:int
    entries_in_pending_read_request:List[DatastoreEntry]

    def __init__(self, protocol: Protocol, dispatcher: RequestDispatcher, datastore: Datastore, read_priority: int, write_priority: int):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dispatcher = dispatcher
        self.protocol = protocol
        self.datastore = datastore
        self.read_priority = read_priority
        self.write_priority = write_priority
        self.datastore.add_watch_callback(WatchCallback(self.the_watch_callback))
        self.datastore.add_unwatch_callback(WatchCallback(self.the_unwatch_callback))

        self.reset()

    def set_max_request_size(self, max_size:int) -> None:
        self.max_request_size = max_size

    def set_max_response_size(self, max_size:int) -> None:
        self.max_response_size = max_size

    def add_forbidden_region(self, start_addr:int, size:int) -> None:
        self.forbidden_regions.append((start_addr, size))

    def add_readonly_region(self, start_addr:int, size:int) -> None:
        self.readonly_regions.append((start_addr, size))

    def the_watch_callback(self, entry_id:str) -> None:
        entry = self.datastore.get_entry(entry_id)
        self.watched_entries_sorted_by_address.add(DataStoreEntrySortableByAddress(entry))

    def the_unwatch_callback(self, entry_id:str) -> None:
        if len(self.datastore.get_watchers(entry_id)) == 0:
            entry = self.datastore.get_entry(entry_id)
            self.watched_entries_sorted_by_address.discard(DataStoreEntrySortableByAddress(entry))

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stop_requested = True

    def reset(self) -> None:
        self.stop_requested = False
        self.read_request_pending = False
        self.started = False

        self.max_request_size = self.DEFAULT_MAX_REQUEST_SIZE
        self.max_response_size = self.DEFAULT_MAX_RESPONSE_SIZE
        self.forbidden_regions = []
        self.readonly_regions = []

        self.watched_entries_sorted_by_address = SortedSet()
        self.read_cursor = 0
        self.entries_in_pending_read_request = []

    def process(self) -> None:
        if not self.started:
            self.reset()
            return
        elif self.stop_requested and not self.read_request_pending:
            self.reset()
            return

        if not self.read_request_pending:
            request, entries_in_request = self.make_next_read_request()
            if request is not None:
                self.logger.debug('Registering a request for %d datastore entries. %s' % (len(entries_in_request), request))
                self.dispatcher.register_request(
                    request=request,
                    success_callback=SuccessCallback(self.read_success_callback),
                    failure_callback=FailureCallback(self.read_failure_callback),
                    priority=self.read_priority
                )
                self.read_request_pending = True
                self.entries_in_pending_read_request = entries_in_request

    def make_next_read_request(self) -> Tuple[Optional[Request], List[DatastoreEntry]]:
        """
        This method generate a read request by moving in a list of watched entries
        It works in a round-robin scheme and will agglomerate entries that are contiguous in memory
        """
        max_block_per_request:int = (self.max_request_size - Request.OVERHEAD_SIZE) // self.protocol.read_memory_request_size_per_block()
        entries_in_request:List[DatastoreEntry] = []
        block_list:List[Tuple[int,int]] = []
        skipped_entries_count = 0
        clusters_in_request:List[Cluster] = [] 

        memory_to_read = MemoryContent(retain_data=False) # We'll use that for agglomeration
        while len(entries_in_request) + skipped_entries_count < len(self.watched_entries_sorted_by_address):
            candidate_entry = self.watched_entries_sorted_by_address[self.read_cursor].entry    # .entry because we use a wrapper for SortedSet
            must_skip = False
            
            # Check for forbidden region
            is_in_forbidden_region = False
            for region in self.forbidden_regions:
                region_start = region[0]
                region_end = region_start + region[1]-1
                entry_start = candidate_entry.get_address()
                entry_end = entry_start + candidate_entry.get_size()-1
                
                if not (entry_end < region_start or entry_start > region_end):
                    is_in_forbidden_region = True
                    break

            if is_in_forbidden_region:
                must_skip = True

            # Check if must skip
            if must_skip:
                skipped_entries_count +=1
                continue
            
            memory_to_read.add_empty(candidate_entry.get_address(), candidate_entry.get_size())
            clusters_candidate = memory_to_read.get_cluster_list_no_data_by_address()

            if len(clusters_candidate) > max_block_per_request:
                break # No space in request

            # Check response size limit
            response_size = Response.OVERHEAD_SIZE
            for cluster in clusters_candidate:
                response_size += self.protocol.read_memory_response_overhead_size_per_block()
                response_size += cluster.size

            if response_size > self.max_response_size:
                break   # No space in response

            # We can fit the data so far..  latch the list of cluster and add the candidate to the entries to be updated
            clusters_in_request = copy.copy(clusters_candidate)
            entries_in_request.append(candidate_entry)   # Remember what entries is involved so we can update value once response is received

            self.read_cursor += 1
            if self.read_cursor >= len(self.watched_entries_sorted_by_address):
                self.read_cursor = 0

        block_list = []
        for cluster in clusters_in_request:
            block_list.append( (cluster.start_addr, cluster.size) )

        request = self.protocol.read_memory_blocks(block_list) if len(block_list) > 0 else None
        return (request, entries_in_request)


    def read_success_callback(self, request: Request, response:Response, params: Any = None) -> None:
        self.logger.debug("Success callback. Request=%s. Response Code=%s, Params=%s" % (request, response.code, params))

        if response.code == ResponseCode.OK:
            response_data = self.protocol.parse_response(response)
            if response_data['valid']:
                try:
                    temp_memory = MemoryContent()
                    for block in response_data['read_blocks']:
                        temp_memory.write(block['address'], block['data'])
                            
                    for entry in self.entries_in_pending_read_request:
                        raw_data = temp_memory.read(entry.get_address(), entry.get_size())
                        entry.set_value_from_data(raw_data)
                except Exception as e:
                    self.logger.critical('Error while writing datastore. %s' % str(e))
                    self.logger.debug(traceback.format_exc())
            else:
                self.logger.error('Response for ReadMemory read request is malformed and must be discared.')                
        else:
            self.logger.warning('Response for ReadMemory has been refused with response code %s.' % response.code)

        self.read_completed()

    def read_failure_callback(self, request: Request, params: Any = None) -> None:
        self.logger.debug("Failure callback. Request=%s. Params=%s" % (request, params))
        self.logger.error('Failed to get a response for ReadMemory request.')

        self.read_completed()

    def read_completed(self) -> None:
        self.read_request_pending = False
