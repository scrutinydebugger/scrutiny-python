#    test_memory_reader.py
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import unittest
import random
from dataclasses import dataclass
from sortedcontainers import SortedSet

from scrutiny.server.datastore import Datastore, DatastoreEntry
from scrutiny.server.device.request_generator.memory_reader import MemoryReader, DataStoreEntrySortableByAddress
from scrutiny.server.device.request_dispatcher import RequestDispatcher
from scrutiny.server.protocol import Protocol, Request, Response
from scrutiny.server.protocol.commands import *
from scrutiny.core.variable import *

from typing import List, Dict
from scrutiny.core.typehints import GenericCallback


class BlockToRead:
    address: int
    nfloat: int
    entries: List[DatastoreEntry]

    def __init__(self, address: int, nfloat: int, entries: List[DatastoreEntry]):
        self.address = address
        self.nfloat = nfloat
        self.entries = entries

    def __repr__(self):
        return '<Block: 0x%08x with %d float>' % (self.address, self.nfloat)


def make_dummy_entries(address, n, vartype=VariableType.float32):
    for i in range(n):
        dummy_var = Variable('dummy', vartype=vartype, path_segments=['a', 'b', 'c'],
                             location=address + i * vartype.get_size_bit() // 8, endianness=Endianness.Little)
        entry = DatastoreEntry(DatastoreEntry.EntryType.Var, 'path_%d' % i, variable_def=dummy_var)
        yield entry


def d2f(d):
    return struct.unpack('f', struct.pack('f', d))[0]


class TestMemoryReaderBasicReadOperation(unittest.TestCase):
    # Make sure that the entries are sortable by address with the thirdparty SortedSet object

    def test_sorted_set(self):
        theset = SortedSet()
        entries = list(make_dummy_entries(1000, 5))
        entries += list(make_dummy_entries(0, 5))
        for entry in entries:
            theset.add(DataStoreEntrySortableByAddress(entry))
        for entry in entries:
            theset.add(DataStoreEntrySortableByAddress(entry))

        self.assertEqual(len(theset), len(entries))
        entries_sorted = [v.entry.get_address() for v in theset]
        is_sorted = all(entries_sorted[i] <= entries_sorted[i + 1] for i in range(len(entries_sorted) - 1))
        self.assertTrue(is_sorted)

        for entry in entries:
            theset.discard(DataStoreEntrySortableByAddress(entry))

        self.assertEqual(len(theset), 0)

    def generic_test_read_block_sequence(self, expected_blocks_sequence, reader, dispatcher, protocol, niter=5):
        for i in range(niter):
            for expected_block_list in expected_blocks_sequence:
                expected_block_list.sort(key=lambda x: x.address)
                reader.process()
                dispatcher.process()

                req_record = dispatcher.pop_next()
                self.assertIsNotNone(req_record, 'iter=%d' % i)
                self.assertIsNone(dispatcher.pop_next(), 'iter=%d' % i)
                req = req_record.request  # That out request

                # Make sure that nothing happens until this request is completed.
                reader.process()
                dispatcher.process()
                self.assertIsNone(dispatcher.pop_next(), 'iter=%d' % i)

                # First request should be a read of the 2 first blocks
                self.assertEqual(req.command, MemoryControl, 'iter=%d' % i)
                self.assertEqual(MemoryControl.Subfunction(req.subfn), MemoryControl.Subfunction.Read, 'iter=%d' % i)

                # Make sure the request contains the 2 expected blocks
                request_data = protocol.parse_request(req)
                self.assertEqual(len(request_data['blocks_to_read']), len(expected_block_list), 'iter=%d' % i)
                j = 0
                for expected_block in expected_block_list:
                    self.assertEqual(request_data['blocks_to_read'][j]['address'], expected_block.address, 'iter=%d, block=%d' % (i, j))
                    self.assertEqual(request_data['blocks_to_read'][j]['length'], expected_block.nfloat * 4, 'iter=%d, block=%d' % (i, j))
                    j += 1

                # Simulate that the response has been received
                block_list = []
                data_lut: Dict[BlockToRead, List[float]] = {}  # To remember to random value we'll generate
                for expected_block in expected_block_list:
                    values = [d2f(random.random()) for x in range(expected_block.nfloat)]
                    data_lut[expected_block] = values   # Remember for assertion later
                    block_data = struct.pack('<' + 'f' * expected_block.nfloat, *values)    # Make memory dump
                    block_list.append((expected_block.address, block_data))

                response = protocol.respond_read_memory_blocks(block_list);
                req_record.complete(success=True, response=response)
                # By completing the request. Success callback should be called making the datastore reader update the datastore

                for expected_block in expected_block_list:
                    values = data_lut[expected_block]  # Get back our value list
                    for j in range(len(expected_block.entries)):
                        # Let's validate that the datastore is updated
                        self.assertEqual(expected_block.entries[j].get_value(), values[j], 'iter=%d, block=%d' % (i, j))

    def test_read_request_basic_behavior(self):
        # Here we have a set of datastore entries that are contiguous in memory.
        # We read them all in a single block (no limitation) and make sure the values are good.
        # We expect the datastore reader to keep asking for updates, so we run the sequence 5 times

        nfloat = 100
        address = 0x1000
        ds = Datastore()
        entries = list(make_dummy_entries(address=address, n=nfloat, vartype=VariableType.float32))
        ds.add_entries(entries)
        dispatcher = RequestDispatcher()

        protocol = Protocol(1, 0)
        protocol.set_address_size_bits(32)
        reader = MemoryReader(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        reader.set_max_request_size(1024)  # big enough for all of them
        reader.set_max_response_size(1024)  # big enough for all of them
        reader.start()

        for entry in entries:
            ds.start_watching(entry, 'unittest', GenericCallback(lambda *args, **kwargs: None))

        expected_blocks_sequence = [
            [BlockToRead(address, nfloat, entries)]
        ]

        self.generic_test_read_block_sequence(expected_blocks_sequence, reader, dispatcher, protocol, niter=5)

    def test_read_request_multiple_blocks_2blocks_per_req(self):
        # Here, we define 3 non-contiguous block of memory and impose a limit on the request size to allow only 2 blocks read per request.
        # We make sure that blocks are completely read.

        nfloat1 = 10
        nfloat2 = 20
        nfloat3 = 30
        address1 = 0x1000
        address2 = 0x2000
        address3 = 0x3000
        ds = Datastore()
        entries1 = list(make_dummy_entries(address=address1, n=nfloat1, vartype=VariableType.float32))
        entries2 = list(make_dummy_entries(address=address2, n=nfloat2, vartype=VariableType.float32))
        entries3 = list(make_dummy_entries(address=address3, n=nfloat3, vartype=VariableType.float32))
        all_entries = entries1 + entries2 + entries3
        ds.add_entries(all_entries)
        dispatcher = RequestDispatcher()
        protocol = Protocol(1, 0)
        reader = MemoryReader(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        reader.set_max_request_size(Request.OVERHEAD_SIZE + protocol.read_memory_request_size_per_block() * 2)  # 2 block per request
        reader.set_max_response_size(1024)  # Non-limiting here
        reader.start()

        for entry in all_entries:
            ds.start_watching(entry, 'unittest', GenericCallback(lambda *args, **kwargs: None))

        # The expected sequence of block will be : 1,2 - 3,1 - 2,3 - 1,2 - etc
        expected_blocks_sequence = [
            [BlockToRead(address1, nfloat1, entries1), BlockToRead(address2, nfloat2, entries2)],
            [BlockToRead(address3, nfloat3, entries3), BlockToRead(address1, nfloat1, entries1)],
            [BlockToRead(address2, nfloat2, entries2), BlockToRead(address3, nfloat3, entries3)]
        ]

        self.generic_test_read_block_sequence(expected_blocks_sequence, reader, dispatcher, protocol, niter=5)

    def test_read_request_multiple_blocks_limited_by_response_size(self):
        # Here we make read entries, but response has enough space for only 10 blocks of 1 entry.
        # Make sure this happens

        nfloat = 15
        entries = []
        for i in range(nfloat):
            entries += list(make_dummy_entries(address=i * 0x100, n=1, vartype=VariableType.float32))

        ds = Datastore()
        ds.add_entries(entries)

        dispatcher = RequestDispatcher()
        protocol = Protocol(1, 0)
        reader = MemoryReader(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        reader.set_max_request_size(1024)  # Non-limiting here
        reader.set_max_response_size(Response.OVERHEAD_SIZE + protocol.read_memory_response_overhead_size_per_block() * 10 + 4 * 10)
        reader.start()

        for entry in entries:
            ds.start_watching(entry, 'unittest', GenericCallback(lambda *args, **kwargs: None))

        # The expected sequence of block will be : 1,2 - 3,1 - 2,3 - 1,2 - etc
        # Sorted by address.
        expected_blocks_sequence = [
            [BlockToRead(i * 0x100, 1, entries[i:i + 1]) for i in range(10)],
            [BlockToRead((10 + i) * 0x100, 1, entries[10 + i:10 + i + 1])
             for i in range(5)] + [BlockToRead(i * 0x100, 1, entries[i:i + 1]) for i in range(5)],
            [BlockToRead((i + 5) * 0x100, 1, entries[5 + i:5 + i + 1]) for i in range(10)]
        ]

        self.generic_test_read_block_sequence(expected_blocks_sequence, reader, dispatcher, protocol, niter=5)

    def test_request_size_limit(self):
        # Make sure the maximum request size is always respected

        entries = []
        for i in range(20):  # different variable size
            entries += list(make_dummy_entries(address=i * 0x100, n=1, vartype=VariableType.uint64))
            entries += list(make_dummy_entries(address=i * 0x100 + 8, n=1, vartype=VariableType.uint32))
            entries += list(make_dummy_entries(address=i * 0x100 + 8 + 4, n=1, vartype=VariableType.uint16))
            entries += list(make_dummy_entries(address=i * 0x100 + 8 + 4 + 2, n=1, vartype=VariableType.uint8))

        # Setup everything
        ds = Datastore()
        ds.add_entries(entries)
        dispatcher = RequestDispatcher()
        protocol = Protocol(1, 0)
        reader = MemoryReader(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        reader.set_max_request_size(1024)
        reader.set_max_response_size(1024)
        reader.start()

        # We need to watch the variable so that they are read
        for entry in entries:
            ds.start_watching(entry, 'unittest', callback=GenericCallback(lambda *args, **kwargs: None))

        # try many different possible size
        for max_request_size in range(32, 128):
            for i in range(20):  # repeat multiple time, just to be sure to wrap around the entries.
                reader.set_max_request_size(max_request_size)
                reader.process()
                dispatcher.process()

                record = dispatcher.pop_next()
                self.assertIsNotNone(record)
                self.assertLessEqual(record.request.size(), max_request_size)   # That's the main test

                # Respond the request so that we can a new request coming in
                request_data = protocol.parse_request(record.request)
                response_block = []
                for block in request_data['blocks_to_read']:
                    response_block.append((block['address'], b'\x00' * block['length']))

                response = protocol.respond_read_memory_blocks(response_block)
                record.complete(success=True, response=response)

    def test_response_size_limit(self):
        # Make sure the maximum response size is always respected

        entries = []
        for i in range(20):     # Try different size of variable
            entries += list(make_dummy_entries(address=i * 0x100, n=1, vartype=VariableType.uint64))
            entries += list(make_dummy_entries(address=i * 0x100 + 8, n=1, vartype=VariableType.uint32))
            entries += list(make_dummy_entries(address=i * 0x100 + 8 + 4, n=1, vartype=VariableType.uint16))
            entries += list(make_dummy_entries(address=i * 0x100 + 8 + 4 + 2, n=1, vartype=VariableType.uint8))

        # Setup everything
        ds = Datastore()
        ds.add_entries(entries)
        dispatcher = RequestDispatcher()
        protocol = Protocol(1, 0)
        reader = MemoryReader(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        reader.set_max_request_size(1024)
        reader.set_max_response_size(1024)
        reader.start()

        for entry in entries:
            ds.start_watching(entry, 'unittest', callback=GenericCallback(lambda *args, **kwargs: None))

        # Try multiple max_size
        for max_response_size in range(32, 128):
            for i in range(20):  # repeat multiple time just tu be sure. Will do all entries and wrap
                reader.set_max_response_size(max_response_size)
                reader.process()
                dispatcher.process()

                record = dispatcher.pop_next()
                self.assertIsNotNone(record)

                # Respond the request so that we can a new request coming in
                request_data = protocol.parse_request(record.request)
                response_block = []
                for block in request_data['blocks_to_read']:
                    response_block.append((block['address'], b'\x00' * block['length']))

                response = protocol.respond_read_memory_blocks(response_block)
                self.assertLessEqual(response.size(), max_response_size)    # That's the main test
                record.complete(success=True, response=response)


class TestMemoryReaderComplexReadOperation(unittest.TestCase):
    # Here we make a complex pattern of variables to read.
    # Different types,  different blocks, forbidden regions, request and response size limit.
    # We make sure that all entries are updated in a round robin scheme.
    # So everyone is updated. Nobody is updated twice unless everybody else us updated.

    def setUp(self):
        self.callback_count_map = {}

    def init_count_map(self, all_entries):
        for entry in all_entries:
            self.callback_count_map[entry] = 0

    def value_change_callback1(self, owner, entry):
        if entry not in self.callback_count_map:
            self.callback_count_map[entry] = 0

        self.callback_count_map[entry] += 1

    def get_callback_count_min_max(self, exclude_entries=[]):
        low = None
        high = None

        for entry in self.callback_count_map:
            if entry in exclude_entries:
                continue

            v = self.callback_count_map[entry]
            if low is None or v < low:
                low = v

            if high is None or v > high:
                high = v

        return (low, high)

    def test_read_request_multiple_blocks_complex_pattern(self):
        max_request_size = 128
        max_response_size = 128
        forbidden_region_start = 0x4101
        forbidden_region_end = 0x413D

        # Generate a complex patterns of datastore entries
        entries = list(make_dummy_entries(address=0x1000, n=1, vartype=VariableType.float32))
        entries += list(make_dummy_entries(address=0x1004, n=2, vartype=VariableType.uint16))
        entries += list(make_dummy_entries(address=0x2000, n=0x100, vartype=VariableType.sint8))
        entries += list(make_dummy_entries(address=0x2100, n=0x100, vartype=VariableType.uint8))
        entries += list(make_dummy_entries(address=0x2200, n=0x100, vartype=VariableType.boolean))
        entries += list(make_dummy_entries(address=0x3000, n=0x100, vartype=VariableType.uint32))
        entries += list(make_dummy_entries(address=0x4000, n=0x100, vartype=VariableType.uint8))
        forbidden_entries = list(make_dummy_entries(address=0x4100, n=0x10, vartype=VariableType.uint32))
        entries += forbidden_entries
        entries += list(make_dummy_entries(address=0x4140, n=0x10, vartype=VariableType.uint8))

        for i in range(0x100):
            entries += list(make_dummy_entries(address=0x10000 + i * 0x10, n=1, vartype=VariableType.uint8))

        # This will count the number of time the value is changed in the datastore
        self.init_count_map(entries)

        # Setup everything
        ds = Datastore()
        ds.add_entries(entries)
        dispatcher = RequestDispatcher()
        protocol = Protocol(1, 0)
        reader = MemoryReader(protocol=protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        reader.set_max_request_size(128)
        reader.set_max_response_size(128)
        reader.add_forbidden_region(forbidden_region_start, forbidden_region_end - forbidden_region_start + 1)
        reader.start()

        # Watch all entries so that they are all read
        for entry in entries:
            ds.start_watching(entry, 'unittest', GenericCallback(self.value_change_callback1))

        # We process the reader until we do 10 round of updates or something fails
        max_loop = 10000
        loop_count = 0
        while loop_count < max_loop:
            reader.process()
            dispatcher.process()

            record = dispatcher.pop_next()
            self.assertIsNotNone(record)

            self.assertLessEqual(record.request.size(), max_request_size)
            response_block = []
            request_data = protocol.parse_request(record.request)
            self.assertTrue(request_data['valid'])

            for block in request_data['blocks_to_read']:
                in_allowed_region = block['address'] > forbidden_region_end or (block['address'] + block['length'] < forbidden_region_start)
                self.assertTrue(in_allowed_region)
                response_block.append((block['address'], b'\x00' * block['length']))

            response = protocol.respond_read_memory_blocks(response_block)
            self.assertLessEqual(response.size(), max_response_size)
            record.complete(success=True, response=response)

            low, high = self.get_callback_count_min_max(exclude_entries=forbidden_entries)
            self.assertIsNotNone(low)
            self.assertIsNotNone(high)
            self.assertGreaterEqual(high, low)    # High should be greater than low
            self.assertLessEqual(high - low, 1)     # High should be equal to low or low+1. This ensure that round robin is working fine

            if low > 10:
                break

            loop_count += 1

        self.assertLess(loop_count, max_loop)  # Make sure we haven't exited because nothing happens

        # Make sure no entries touching the forbidden region is being updated
        for forbidden_entry in forbidden_entries:
            self.assertEqual(self.callback_count_map[forbidden_entry], 0)
