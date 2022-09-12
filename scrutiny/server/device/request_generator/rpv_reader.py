#    rpv_reader.py
#        Make requests to write Runtime Published values from the device.
#        This feature requires a different protocol message than Memory Write
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import logging
import copy
import traceback
from sortedcontainers import SortedSet  # type: ignore
from scrutiny.server.datastore.datastore_entry import DatastoreRPVEntry

from scrutiny.server.protocol import *
import scrutiny.server.protocol.typing as protocol_typing
from scrutiny.server.device.request_dispatcher import RequestDispatcher, SuccessCallback, FailureCallback
from scrutiny.server.datastore import Datastore, DatastoreVariableEntry, WatchCallback
from scrutiny.core.memory_content import MemoryContent, Cluster

from typing import Any, List, Set, Tuple, Optional, cast, Dict


class DataStoreEntrySortableByRpvId:
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


class RPVReader:

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
    watched_entries_ordered_by_id: SortedSet
    read_cursor: int
    entries_in_pending_read_request: Dict[int, DatastoreRPVEntry]

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
        self.max_request_payload_size = max_size

    def set_max_response_payload_size(self, max_size: int) -> None:
        self.max_response_payload_size = max_size

    def set_size_limits(self, max_request_payload_size: int, max_response_payload_size: int) -> None:
        self.set_max_request_payload_size(max_request_payload_size)
        self.set_max_response_payload_size(max_response_payload_size)

    def the_watch_callback(self, entry_id: str) -> None:
        entry = self.datastore.get_entry(entry_id)
        if isinstance(entry, DatastoreRPVEntry):
            self.watched_entries_ordered_by_id.add(DataStoreEntrySortableByRpvId(entry))

    def the_unwatch_callback(self, entry_id: str) -> None:
        if len(self.datastore.get_watchers(entry_id)) == 0:
            entry = self.datastore.get_entry(entry_id)
            if isinstance(entry, DatastoreRPVEntry):
                self.watched_entries_ordered_by_id.discard(DataStoreEntrySortableByRpvId(entry))

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

        self.watched_entries_ordered_by_id = SortedSet()
        self.read_cursor = 0
        self.entries_in_pending_read_request = {}

    def process(self) -> None:
        if not self.started:
            self.reset()
            return
        elif self.stop_requested and not self.request_pending:
            self.reset()
            return

        if not self.request_pending:
            request, entries_in_request = self.make_next_read_request()
            if request is not None:
                self.logger.debug('Registering a RPVRead request for %d datastore entries. %s' % (len(entries_in_request), request))
                self.dispatcher.register_request(
                    request=request,
                    success_callback=SuccessCallback(self.success_callback),
                    failure_callback=FailureCallback(self.failure_callback),
                    priority=self.request_priority
                )
                self.request_pending = True
                self.entries_in_pending_read_request = {}
                for entry in entries_in_request:
                    self.entries_in_pending_read_request[entry.get_rpv().id] = entry

    def make_next_read_request(self) -> Tuple[Optional[Request], List[DatastoreRPVEntry]]:
        entries_in_request: List[DatastoreRPVEntry] = []
        if self.read_cursor >= len(self.watched_entries_ordered_by_id):
            self.read_cursor = 0

        while len(entries_in_request) < len(self.watched_entries_ordered_by_id):
            next_entry = self.watched_entries_ordered_by_id[self.read_cursor].entry
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
            self.read_cursor += 1
            if self.read_cursor >= len(self.watched_entries_ordered_by_id):
                self.read_cursor = 0

        ids = [x.get_rpv().id for x in entries_in_request]
        request = self.protocol.read_runtime_published_values(ids) if len(ids) > 0 else None
        return (request, entries_in_request)

    def success_callback(self, request: Request, response: Response, params: Any = None) -> None:
        self.logger.debug("Success callback. Response=%s, Params=%s" % (response, params))

        if response.code == ResponseCode.OK:
            try:
                response_data = cast(protocol_typing.Response.MemoryControl.ReadRPV, self.protocol.parse_response(response))
                try:
                    for read_rpv in response_data['read_rpv']:
                        if read_rpv['id'] not in self.entries_in_pending_read_request:
                            self.logger.error('Received data for RPV ID=0x%x but this Id was not requested' % (read_rpv['id']))
                        else:
                            entry = self.entries_in_pending_read_request[read_rpv['id']]
                            entry.set_value(read_rpv['data'])
                except Exception as e:
                    self.logger.critical('Error while writing datastore. %s' % str(e))
                    self.logger.debug(traceback.format_exc())
            except:
                self.logger.error('Response for ReadRPV read request is malformed and must be discared.')
                self.logger.debug(traceback.format_exc())
        else:
            self.logger.warning('Response for ReadRPV has been refused with response code %s.' % response.code)

        self.read_completed()

    def failure_callback(self, request: Request, params: Any = None) -> None:
        self.logger.debug("Failure callback. Request=%s. Params=%s" % (request, params))
        self.logger.error('Failed to get a response for ReadRPV request.')

        self.read_completed()

    def read_completed(self) -> None:
        self.request_pending = False
