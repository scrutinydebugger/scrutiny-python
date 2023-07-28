#    test_memory_reader.py
#        Make sure the memory_Reader correctly reads the device memory to fills the datastore
#        entries that are watch
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2023 Scrutiny Debugger

import random
from dataclasses import dataclass
from sortedcontainers import SortedSet  # type: ignore

from scrutiny.server.datastore.datastore import Datastore
from scrutiny.server.datastore.datastore_entry import *
from scrutiny.server.datastore.entry_type import EntryType
from scrutiny.server.device.submodules.memory_reader import MemoryReader, DataStoreEntrySortableByAddress, DataStoreEntrySortableByRpvId
from scrutiny.server.device.request_dispatcher import RequestDispatcher
from scrutiny.server.protocol import Protocol, Request, Response
import scrutiny.server.protocol.typing as protocol_typing
from scrutiny.server.protocol.commands import *
from scrutiny.core.variable import *
from scrutiny.core.basic_types import *
from test import ScrutinyUnitTest

from typing import List, Dict, Generator, cast
from scrutiny.core.typehints import GenericCallback


class BlockToRead:
    address: int
    nfloat: int
    entries: List[DatastoreVariableEntry]

    def __init__(self, address: int, nfloat: int, entries: List[DatastoreVariableEntry]):
        self.address = address
        self.nfloat = nfloat
        self.entries = entries

    def __repr__(self):
        return '<Block: 0x%08x with %d float>' % (self.address, self.nfloat)


def generate_random_value(datatype: EmbeddedDataType) -> Encodable:
    # Generate random bitstring of the right size. Then decode it.
    codec = Codecs.get(datatype, Endianness.Big)
    if datatype in [EmbeddedDataType.float8, EmbeddedDataType.float16, EmbeddedDataType.float32, EmbeddedDataType.float64, EmbeddedDataType.float128, EmbeddedDataType.float256]:
        return codec.decode(codec.encode((random.random() - 0.5) * 1000))

    bytestr = bytes([random.randint(0, 0xff) for i in range(datatype.get_size_byte())])
    return codec.decode(bytestr)


def make_dummy_var_entries(address, n, vartype=EmbeddedDataType.float32):
    for i in range(n):
        dummy_var = Variable('dummy', vartype=vartype, path_segments=['a', 'b', 'c'],
                             location=address + i * vartype.get_size_bit() // 8, endianness=Endianness.Little)
        entry = DatastoreVariableEntry('path_%d' % i, variable_def=dummy_var)
        yield entry


def make_dummy_rpv_entries(start_id, n, vartype=EmbeddedDataType.float32) -> Generator[DatastoreRPVEntry, None, None]:
    for i in range(n):
        rpv = RuntimePublishedValue(id=start_id + i, datatype=vartype)
        entry = DatastoreRPVEntry('rpv_%d' % i, rpv=rpv)
        yield entry


def d2f(d):
    return struct.unpack('f', struct.pack('f', d))[0]


class TestMemoryReaderBasicReadOperation(ScrutinyUnitTest):
    """
        Test the memory reader for its ability to read memory block using the MemoryControl.Read request.
        Basic read operation only
    """
    # Make sure that the entries are sortable by address with the thirdparty SortedSet object

    def test_sorted_set(self):
        theset = SortedSet()
        entries = list(make_dummy_var_entries(1000, 5))
        entries += list(make_dummy_var_entries(0, 5))
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

    def generic_test_read_block_sequence(self, expected_blocks_sequence: List[List[BlockToRead]], reader: MemoryReader, dispatcher: RequestDispatcher, protocol: Protocol, niter: int = 5):
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
                request_data = cast(protocol_typing.Request.MemoryControl.Read, protocol.parse_request(req))
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
        entries = list(make_dummy_var_entries(address=address, n=nfloat, vartype=EmbeddedDataType.float32))
        ds.add_entries(entries)
        dispatcher = RequestDispatcher()

        protocol = Protocol(1, 0)
        protocol.set_address_size_bits(32)
        reader = MemoryReader(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        reader.set_max_request_payload_size(1024)  # big enough for all of them
        reader.set_max_response_payload_size(1024)  # big enough for all of them
        reader.start()

        for entry in entries:
            ds.start_watching(entry, 'unittest')

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
        entries1 = list(make_dummy_var_entries(address=address1, n=nfloat1, vartype=EmbeddedDataType.float32))
        entries2 = list(make_dummy_var_entries(address=address2, n=nfloat2, vartype=EmbeddedDataType.float32))
        entries3 = list(make_dummy_var_entries(address=address3, n=nfloat3, vartype=EmbeddedDataType.float32))
        all_entries = entries1 + entries2 + entries3
        ds.add_entries(all_entries)
        dispatcher = RequestDispatcher()
        protocol = Protocol(1, 0)
        reader = MemoryReader(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        reader.set_max_request_payload_size(protocol.read_memory_request_size_per_block() * 2)  # 2 block per request
        reader.set_max_response_payload_size(1024)  # Non-limiting here
        reader.start()

        for entry in all_entries:
            ds.start_watching(entry, 'unittest')

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
            entries += list(make_dummy_var_entries(address=i * 0x100, n=1, vartype=EmbeddedDataType.float32))

        ds = Datastore()
        ds.add_entries(entries)

        dispatcher = RequestDispatcher()
        protocol = Protocol(1, 0)
        reader = MemoryReader(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        reader.set_max_request_payload_size(1024)  # Non-limiting here
        reader.set_max_response_payload_size(protocol.read_memory_response_overhead_size_per_block() * 10 + 4 * 10)
        reader.start()

        for entry in entries:
            ds.start_watching(entry, 'unittest')

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
            entries += list(make_dummy_var_entries(address=i * 0x100, n=1, vartype=EmbeddedDataType.uint64))
            entries += list(make_dummy_var_entries(address=i * 0x100 + 8, n=1, vartype=EmbeddedDataType.uint32))
            entries += list(make_dummy_var_entries(address=i * 0x100 + 8 + 4, n=1, vartype=EmbeddedDataType.uint16))
            entries += list(make_dummy_var_entries(address=i * 0x100 + 8 + 4 + 2, n=1, vartype=EmbeddedDataType.uint8))

        # Setup everything
        ds = Datastore()
        ds.add_entries(entries)
        dispatcher = RequestDispatcher()
        protocol = Protocol(1, 0)
        reader = MemoryReader(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        reader.set_max_request_payload_size(1024)
        reader.set_max_response_payload_size(1024)
        reader.start()

        # We need to watch the variable so that they are read
        for entry in entries:
            ds.start_watching(entry, 'unittest')

        # try many different possible size
        for max_request_size in range(32, 128):
            for i in range(20):  # repeat multiple time, just to be sure to wrap around the entries.
                reader.set_max_request_payload_size(max_request_size)
                reader.process()
                dispatcher.process()

                record = dispatcher.pop_next()
                self.assertIsNotNone(record)
                self.assertLessEqual(record.request.data_size(), max_request_size)   # That's the main test

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
            entries += list(make_dummy_var_entries(address=i * 0x100, n=1, vartype=EmbeddedDataType.uint64))
            entries += list(make_dummy_var_entries(address=i * 0x100 + 8, n=1, vartype=EmbeddedDataType.uint32))
            entries += list(make_dummy_var_entries(address=i * 0x100 + 8 + 4, n=1, vartype=EmbeddedDataType.uint16))
            entries += list(make_dummy_var_entries(address=i * 0x100 + 8 + 4 + 2, n=1, vartype=EmbeddedDataType.uint8))

        # Setup everything
        ds = Datastore()
        ds.add_entries(entries)
        dispatcher = RequestDispatcher()
        protocol = Protocol(1, 0)
        reader = MemoryReader(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        reader.set_max_request_payload_size(1024)
        reader.set_max_response_payload_size(1024)
        reader.start()

        for entry in entries:
            ds.start_watching(entry, 'unittest')

        # Try multiple max_size
        for max_response_payload_size in range(32, 128):
            for i in range(20):  # repeat multiple time just tu be sure. Will do all entries and wrap
                reader.set_max_response_payload_size(max_response_payload_size)
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
                self.assertLessEqual(response.data_size(), max_response_payload_size)    # That's the main test
                record.complete(success=True, response=response)


class TestMemoryReaderComplexReadOperation(ScrutinyUnitTest):
    """
    Test the memory reader for its ability to read memory block by entries using the MemoryControl.Read request.

    Here we make a complex pattern of variables to read.
    Different types,  different blocks, forbidden regions, request and response size limit.
    We make sure that all entries are updated in a round robin scheme.
    So everyone is updated. Nobody is updated twice unless everybody else us updated.
    """

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
        max_response_payload_size = 128
        forbidden_region_start = 0x4101
        forbidden_region_end = 0x413D

        # Generate a complex patterns of datastore entries
        entries = list(make_dummy_var_entries(address=0x1000, n=1, vartype=EmbeddedDataType.float32))
        entries += list(make_dummy_var_entries(address=0x1004, n=2, vartype=EmbeddedDataType.uint16))
        entries += list(make_dummy_var_entries(address=0x2000, n=0x100, vartype=EmbeddedDataType.sint8))
        entries += list(make_dummy_var_entries(address=0x2100, n=0x100, vartype=EmbeddedDataType.uint8))
        entries += list(make_dummy_var_entries(address=0x2200, n=0x100, vartype=EmbeddedDataType.boolean))
        entries += list(make_dummy_var_entries(address=0x3000, n=0x100, vartype=EmbeddedDataType.uint32))
        entries += list(make_dummy_var_entries(address=0x4000, n=0x100, vartype=EmbeddedDataType.uint8))
        forbidden_entries = list(make_dummy_var_entries(address=0x4100, n=0x10, vartype=EmbeddedDataType.uint32))
        entries += forbidden_entries
        entries += list(make_dummy_var_entries(address=0x4140, n=0x10, vartype=EmbeddedDataType.uint8))

        for i in range(0x100):
            entries += list(make_dummy_var_entries(address=0x10000 + i * 0x10, n=1, vartype=EmbeddedDataType.uint8))

        # This will count the number of time the value is changed in the datastore
        self.init_count_map(entries)

        # Setup everything
        ds = Datastore()
        ds.add_entries(entries)
        dispatcher = RequestDispatcher()
        protocol = Protocol(1, 0)
        reader = MemoryReader(protocol=protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        reader.set_max_request_payload_size(128)
        reader.set_max_response_payload_size(128)
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

            for block in request_data['blocks_to_read']:
                in_allowed_region = block['address'] > forbidden_region_end or (block['address'] + block['length'] < forbidden_region_start)
                self.assertTrue(in_allowed_region)
                response_block.append((block['address'], b'\x00' * block['length']))

            response = protocol.respond_read_memory_blocks(response_block)
            self.assertLessEqual(response.data_size(), max_response_payload_size)
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


class TestRawMemoryRead(ScrutinyUnitTest):
    @dataclass
    class CallbackDataContainer:
        call_count: int = 0
        success: Optional[bool] = None
        data: Optional[bytes] = None
        error: Optional[str] = None

    def the_callback(self, request, success, data, error, container: CallbackDataContainer,):
        container.call_count += 1
        container.success = success
        container.data = data
        container.error = error

    def setUp(self):
        self.ds = Datastore()
        self.dispatcher = RequestDispatcher()
        self.protocol = Protocol(1, 0)
        self.reader = MemoryReader(protocol=self.protocol, dispatcher=self.dispatcher, datastore=self.ds, request_priority=0)
        self.reader.set_max_request_payload_size(256)
        self.reader.set_max_response_payload_size(128)
        self.reader.start()

    def test_simple_read(self):
        for i in range(3):
            self.reader.process()
        self.assertIsNone(self.dispatcher.pop_next())

        callback_data = self.CallbackDataContainer()
        self.reader.request_memory_read(0x1000, 257, callback=functools.partial(self.the_callback, container=callback_data))
        payload = bytes([random.randint(0, 255) for i in range(257)])

        for i in range(3):
            cursor = i * 128
            size = 128 if i < 2 else 1

            self.reader.process()
            record = self.dispatcher.pop_next()
            self.assertIsNotNone(record)
            self.assertEqual(record.request.command, MemoryControl)
            self.assertEqual(MemoryControl.Subfunction(record.request.subfn), MemoryControl.Subfunction.Read)
            request_data = cast(protocol_typing.Request.MemoryControl.Read, self.protocol.parse_request(record.request))
            self.assertEqual(len(request_data['blocks_to_read']), 1)
            self.assertEqual(request_data['blocks_to_read'][0]['address'], 0x1000 + cursor)
            self.assertEqual(request_data['blocks_to_read'][0]['length'], size)
            response = self.protocol.respond_read_memory_blocks([(0x1000 + cursor, payload[cursor:cursor + 128])])
            record.complete(True, response)
            if i < 2:
                self.assertEqual(callback_data.call_count, 0)
            else:
                self.assertEqual(callback_data.call_count, 1)
                self.assertTrue(callback_data.success)
                self.assertEqual(callback_data.data, payload)
                self.assertIsNotNone(callback_data.error)

    def test_read_failure(self):
        for i in range(3):
            self.reader.process()
        self.assertIsNone(self.dispatcher.pop_next())

        callback_data = self.CallbackDataContainer()
        self.reader.request_memory_read(0x1000, 257, callback=functools.partial(self.the_callback, container=callback_data))
        payload = bytes([random.randint(0, 255) for i in range(257)])

        for i in range(2):
            cursor = i * 128
            size = 128 if i < 2 else 1

            self.reader.process()
            record = self.dispatcher.pop_next()
            self.assertIsNotNone(record)
            self.assertEqual(record.request.command, MemoryControl)
            self.assertEqual(MemoryControl.Subfunction(record.request.subfn), MemoryControl.Subfunction.Read)
            request_data = cast(protocol_typing.Request.MemoryControl.Read, self.protocol.parse_request(record.request))
            self.assertEqual(len(request_data['blocks_to_read']), 1)
            self.assertEqual(request_data['blocks_to_read'][0]['address'], 0x1000 + cursor)
            self.assertEqual(request_data['blocks_to_read'][0]['length'], size)
            response = self.protocol.respond_read_memory_blocks([(0x1000 + cursor, payload[cursor:cursor + 128])])

            if i == 0:
                record.complete(True, response)
                self.assertEqual(callback_data.call_count, 0)
            else:
                record.complete(False)
                self.assertEqual(callback_data.call_count, 1)
                self.assertFalse(callback_data.success)     # Failure detection
                self.assertIsNone(callback_data.data)
                self.assertIsNotNone(callback_data.error)
                self.assertGreater(len(callback_data.error), 0)

    def test_read_failure_by_nack(self):
        for i in range(3):
            self.reader.process()
        self.assertIsNone(self.dispatcher.pop_next())

        callback_data = self.CallbackDataContainer()
        self.reader.request_memory_read(0x1000, 257, callback=functools.partial(self.the_callback, container=callback_data))
        payload = bytes([random.randint(0, 255) for i in range(257)])

        for i in range(2):
            cursor = i * 128
            size = 128 if i < 2 else 1

            self.reader.process()
            record = self.dispatcher.pop_next()
            self.assertIsNotNone(record)
            self.assertEqual(record.request.command, MemoryControl)
            self.assertEqual(MemoryControl.Subfunction(record.request.subfn), MemoryControl.Subfunction.Read)
            request_data = cast(protocol_typing.Request.MemoryControl.Read, self.protocol.parse_request(record.request))
            self.assertEqual(len(request_data['blocks_to_read']), 1)
            self.assertEqual(request_data['blocks_to_read'][0]['address'], 0x1000 + cursor)
            self.assertEqual(request_data['blocks_to_read'][0]['length'], size)

            if i == 0:
                response = self.protocol.respond_read_memory_blocks([(0x1000 + cursor, payload[cursor:cursor + 128])])
                record.complete(True, response)
                self.assertEqual(callback_data.call_count, 0)
            else:
                response = Response(record.request.command, record.request.subfn, Response.ResponseCode.FailureToProceed)
                record.complete(True, response)
                self.assertEqual(callback_data.call_count, 1)
                self.assertFalse(callback_data.success)     # Failure detection
                self.assertIsNone(callback_data.data)
                self.assertIsNotNone(callback_data.error)
                self.assertGreater(len(callback_data.error), 0)

    def test_read_forbidden_early_fail(self):
        for i in range(3):
            self.reader.process()
        self.assertIsNone(self.dispatcher.pop_next())

        callback_data = self.CallbackDataContainer()
        self.reader.add_forbidden_region(0x1000 - 10, 11)
        self.reader.request_memory_read(0x1000, 257, callback=functools.partial(self.the_callback, container=callback_data))
        self.reader.process()
        self.assertEqual(callback_data.call_count, 1)
        self.assertFalse(callback_data.success)     # Failure detection
        self.assertIsNone(callback_data.data)
        self.assertIsNotNone(callback_data.error)
        self.assertGreater(len(callback_data.error), 0)

    def test_read_multiple_blocks(self):
        max_response_size = 128
        for i in range(3):
            self.reader.process()
        self.assertIsNone(self.dispatcher.pop_next())

        callback_data = self.CallbackDataContainer()
        self.reader.request_memory_read(0x1000, 257, callback=functools.partial(self.the_callback, container=callback_data))
        self.reader.request_memory_read(0x2000, 125, callback=functools.partial(self.the_callback, container=callback_data))
        self.reader.request_memory_read(0x3000, 400, callback=functools.partial(self.the_callback, container=callback_data))
        payload1 = bytes([random.randint(0, 255) for i in range(257)])
        payload2 = bytes([random.randint(0, 255) for i in range(125)])
        payload3 = bytes([random.randint(0, 255) for i in range(400)])

        for msg in range(3):
            if msg == 0:
                payload = payload1
                address = 0x1000
            elif msg == 1:
                payload = payload2
                address = 0x2000
            elif msg == 2:
                payload = payload3
                address = 0x3000

            nchunk = math.ceil(len(payload) / max_response_size)
            for i in range(nchunk):
                cursor = i * max_response_size
                size = min(max_response_size, len(payload) - cursor)

                self.reader.process()
                record = self.dispatcher.pop_next()
                self.assertIsNotNone(record)
                self.assertEqual(record.request.command, MemoryControl)
                self.assertEqual(MemoryControl.Subfunction(record.request.subfn), MemoryControl.Subfunction.Read)
                request_data = cast(protocol_typing.Request.MemoryControl.Read, self.protocol.parse_request(record.request))
                self.assertEqual(len(request_data['blocks_to_read']), 1)
                self.assertEqual(request_data['blocks_to_read'][0]['address'], address + cursor)
                self.assertEqual(request_data['blocks_to_read'][0]['length'], size)
                response = self.protocol.respond_read_memory_blocks([(address + cursor, payload[cursor:cursor + max_response_size])])
                record.complete(True, response)
                if i < nchunk - 1:
                    self.assertEqual(callback_data.call_count, msg)
                else:
                    self.assertEqual(callback_data.call_count, msg + 1)
                    self.assertTrue(callback_data.success)
                    self.assertEqual(callback_data.data, payload)
                    self.assertIsNotNone(callback_data.error)


class TestRPVReaderBasicReadOperation(ScrutinyUnitTest):
    """
        Test the ability to read Runtime Published Values using the MemoryControl.ReadRPV request
    """
    # Make sure that the entries are sortable by ID with the third party SortedSet object

    def test_sorted_set(self):
        theset = SortedSet()
        entries = list(make_dummy_rpv_entries(1000, 5))
        entries += list(make_dummy_rpv_entries(0, 5))
        for entry in entries:
            theset.add(DataStoreEntrySortableByRpvId(entry))
        for entry in entries:
            theset.add(DataStoreEntrySortableByRpvId(entry))

        self.assertEqual(len(theset), len(entries))
        rpv_ids_sorted = [v.entry.get_rpv().id for v in theset]
        is_sorted = all(rpv_ids_sorted[i] <= rpv_ids_sorted[i + 1] for i in range(len(rpv_ids_sorted) - 1))
        self.assertTrue(is_sorted)

        for entry in entries:
            theset.discard(DataStoreEntrySortableByRpvId(entry))

        self.assertEqual(len(theset), 0)

    def generic_test_read_rpv_sequence(self, expected_rpv_entry_sequence: List[List[DatastoreRPVEntry]], reader: MemoryReader, dispatcher: RequestDispatcher, protocol: Protocol, niter: int = 5):
        all_rpvs: List[RuntimePublishedValue] = []
        for sequence_entry in expected_rpv_entry_sequence:
            all_rpvs += [entry.get_rpv() for entry in sequence_entry]
        protocol.configure_rpvs(all_rpvs)

        for i in range(niter):
            for expected_rpv_entry_list in expected_rpv_entry_sequence:
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
                self.assertEqual(MemoryControl.Subfunction(req.subfn), MemoryControl.Subfunction.ReadRPV, 'iter=%d' % i)

                # Make sure the request contains the 2 expected blocks
                request_data = cast(protocol_typing.Request.MemoryControl.ReadRPV, protocol.parse_request(req))
                self.assertEqual(len(request_data['rpvs_id']), len(expected_rpv_entry_list), 'iter=%d' % i)
                j = 0
                for rpv_entry in expected_rpv_entry_list:
                    self.assertEqual(request_data['rpvs_id'][j], rpv_entry.get_rpv().id, 'iter=%d, block=%d' % (i, j))
                    j += 1

                # Simulate that the response has been received
                value_lut: Dict[int, Encodable] = {}  # To remember to random value we'll generate
                expected_rpv_values = []
                for rpv_entry in expected_rpv_entry_list:
                    rpv = rpv_entry.get_rpv()
                    value = generate_random_value(rpv.datatype)
                    value_lut[rpv.id] = value   # Remember for assertion later
                    expected_rpv_values.append((rpv.id, value))

                response = protocol.respond_read_runtime_published_values(vals=expected_rpv_values)
                req_record.complete(success=True, response=response)
                # By completing the request. Success callback should be called making the datastore reader update the datastore

                for rpv_entry in expected_rpv_entry_list:
                    rpv = rpv_entry.get_rpv()
                    self.assertEqual(rpv_entry.get_value(), value_lut[rpv.id], 'iter=%d, RPV=0x%x' % (i, rpv.id))

    def test_read_request_basic_behavior(self):
        # Here we have a set of datastore entries that are contiguous in memory.
        # We read them all in a single block (no limitation) and make sure the values are good.
        # We expect the datastore reader to keep asking for updates, so we run the sequence 5 times

        nfloat = 100
        start_id = 0x1000
        ds = Datastore()
        entries = list(make_dummy_rpv_entries(start_id=start_id, n=nfloat, vartype=EmbeddedDataType.float32))
        ds.add_entries(entries)
        dispatcher = RequestDispatcher()

        protocol = Protocol(1, 0)
        protocol.set_address_size_bits(32)
        reader = MemoryReader(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        reader.set_max_request_payload_size(1024)  # big enough for all of them
        reader.set_max_response_payload_size(1024)  # big enough for all of them
        reader.start()

        for entry in entries:
            ds.start_watching(entry, 'unittest')

        expected_rpv_sequence = [
            entries
        ]

        self.generic_test_read_rpv_sequence(expected_rpv_sequence, reader, dispatcher, protocol, niter=5)

    def test_read_request_multiple_rpvs_2rpvs_per_req(self):
        # Here, we define 3 rpvs and impose a limit on the request size to allow only 2 rpv read per request.
        # We make sure that blocks are completely read.

        start_id = 0x1000
        ds = Datastore()
        entries = list(make_dummy_rpv_entries(start_id=start_id, n=3, vartype=EmbeddedDataType.float32))

        ds.add_entries(entries)
        dispatcher = RequestDispatcher()
        protocol = Protocol(1, 0)
        reader = MemoryReader(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        reader.set_max_request_payload_size(protocol.read_rpv_request_size_per_rpv() * 2)  # 2 rpv per request
        reader.set_max_response_payload_size(1024)  # Non-limiting here
        reader.start()

        for entry in entries:
            ds.start_watching(entry, 'unittest')

        # The expected sequence of block will be : 1,2 - 3,1 - 2,3 - 1,2 - etc
        expected_rpv_entries_sequence = [
            [entries[0], entries[1]],
            [entries[2], entries[0]],
            [entries[1], entries[2]]
        ]

        self.generic_test_read_rpv_sequence(expected_rpv_entries_sequence, reader, dispatcher, protocol, niter=5)

    def test_read_request_multiple_rpvs_limited_by_response_size(self):
        # Here we make read entries, but response has enough space for only 10 rpvs.
        # Make sure this happens

        nfloat = 15
        number_per_req = 10
        entries: List[DatastoreRPVEntry] = []
        entries += list(make_dummy_rpv_entries(start_id=100, n=nfloat, vartype=EmbeddedDataType.float32))

        ds = Datastore()
        ds.add_entries(entries)

        dispatcher = RequestDispatcher()
        protocol = Protocol(1, 0)
        reader = MemoryReader(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        reader.set_max_request_payload_size(1024)  # Non-limiting here
        temp_list = [entry.get_rpv() for entry in entries]
        reader.set_max_response_payload_size(protocol.read_rpv_response_required_size(
            temp_list[0:number_per_req]))    # All RPV are the same type,s o we can do that
        reader.start()

        for entry in entries:
            ds.start_watching(entry, 'unittest')

        # The expected sequence of block will be : 1,2 - 3,1 - 2,3 - 1,2 - etc
        # Sorted by address.
        expected_rpvs_sequence = [
            entries[0:10],
            entries[10:15] + entries[0:5],
            entries[5:15]
        ]

        self.generic_test_read_rpv_sequence(expected_rpvs_sequence, reader, dispatcher, protocol, niter=5)

    def test_request_size_limit(self):
        # Make sure the maximum request size is always respected

        entries: List[DatastoreRPVEntry] = []
        for i in range(20):  # different variable size
            entries += list(make_dummy_rpv_entries(start_id=i * 0x100 + 0, n=1, vartype=EmbeddedDataType.uint64))
            entries += list(make_dummy_rpv_entries(start_id=i * 0x100 + 1, n=1, vartype=EmbeddedDataType.uint32))
            entries += list(make_dummy_rpv_entries(start_id=i * 0x100 + 2, n=1, vartype=EmbeddedDataType.uint16))
            entries += list(make_dummy_rpv_entries(start_id=i * 0x100 + 3, n=1, vartype=EmbeddedDataType.uint8))

        # Setup everything
        ds = Datastore()
        ds.add_entries(entries)
        dispatcher = RequestDispatcher()
        protocol = Protocol(1, 0)
        protocol.configure_rpvs([entry.get_rpv() for entry in entries])
        reader = MemoryReader(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        reader.set_max_request_payload_size(1024)
        reader.set_max_response_payload_size(1024)
        reader.start()

        # We need to watch the variable so that they are read
        for entry in entries:
            ds.start_watching(entry, 'unittest')

        # try many different possible size
        for max_request_payload_size in range(32, 128):
            for i in range(20):  # repeat multiple time, just to be sure to wrap around the entries.
                reader.set_max_request_payload_size(max_request_payload_size)
                reader.process()
                dispatcher.process()

                record = dispatcher.pop_next()
                self.assertIsNotNone(record)
                self.assertLessEqual(record.request.data_size(), max_request_payload_size)   # That's the main test

                # Respond the request so that we can a new request coming in
                request_data = cast(protocol_typing.Request.MemoryControl.ReadRPV, protocol.parse_request(record.request))
                response_vals: List[Tuple[int, Encodable]] = []
                for rpv_id in request_data['rpvs_id']:
                    response_vals.append((rpv_id, int(random.random() * 255)))

                response = protocol.respond_read_runtime_published_values(response_vals)  # Make device hadnler happy so we can continue the test
                record.complete(success=True, response=response)

    def test_response_size_limit(self):
        # Make sure the maximum response size is always respected

        entries: List[DatastoreRPVEntry] = []
        for i in range(20):  # different variable size
            entries += list(make_dummy_rpv_entries(start_id=i * 0x100 + 0, n=1, vartype=EmbeddedDataType.uint64))
            entries += list(make_dummy_rpv_entries(start_id=i * 0x100 + 1, n=1, vartype=EmbeddedDataType.uint32))
            entries += list(make_dummy_rpv_entries(start_id=i * 0x100 + 2, n=1, vartype=EmbeddedDataType.uint16))
            entries += list(make_dummy_rpv_entries(start_id=i * 0x100 + 3, n=1, vartype=EmbeddedDataType.uint8))

        # Setup everything
        ds = Datastore()
        ds.add_entries(entries)
        dispatcher = RequestDispatcher()
        protocol = Protocol(1, 0)
        protocol.configure_rpvs([entry.get_rpv() for entry in entries])
        reader = MemoryReader(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        reader.set_max_request_payload_size(1024)
        reader.set_max_response_payload_size(1024)
        reader.start()

        for entry in entries:
            ds.start_watching(entry, 'unittest')

        # Try multiple max_size
        for max_response_payload_size in range(32, 128):
            for i in range(20):  # repeat multiple time just tu be sure. Will do all entries and wrap
                reader.set_max_response_payload_size(max_response_payload_size)
                reader.process()
                dispatcher.process()

                record = dispatcher.pop_next()
                self.assertIsNotNone(record)

                # Respond the request so that we can a new request coming in
                request_data = cast(protocol_typing.Request.MemoryControl.ReadRPV, protocol.parse_request(record.request))
                response_vals: List[Tuple[int, Encodable]] = []
                for rpv_id in request_data['rpvs_id']:
                    response_vals.append((rpv_id, int(random.random() * 255)))

                response = protocol.respond_read_runtime_published_values(response_vals)
                self.assertLessEqual(response.data_size(), max_response_payload_size)    # That's the main test
                record.complete(success=True, response=response)


class TestAllTypesOfReadMixed(ScrutinyUnitTest):
    """
    Here we test the ability of the MemoryReader to handle mixed subscriptions between RPV, Variables and raw requests
    """

    @dataclass
    class CallbackDataContainer:
        call_count: int = 0
        success: Optional[bool] = None
        data: Optional[bytes] = None
        error: Optional[str] = None

    def raw_read_callback(self, request, success, data, error, container: CallbackDataContainer,):
        container.call_count += 1
        container.success = success
        container.data = data
        container.error = error

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.datastore = Datastore()
        self.protocol = Protocol(1, 0)
        self.callback_counter_per_type: Dict[EntryType, Dict[str, int]] = {}
        self.callback_counter_per_type[EntryType.Var] = {}
        self.callback_counter_per_type[EntryType.RuntimePublishedValue] = {}

    def assert_round_robin(self):
        var_minval = 999
        var_maxval = 0
        for entry_id in self.callback_counter_per_type[EntryType.Var]:
            var_maxval = max(var_maxval, self.callback_counter_per_type[EntryType.Var][entry_id])
            var_minval = min(var_minval, self.callback_counter_per_type[EntryType.Var][entry_id])

        rpv_minval = 999
        rpv_maxval = 0
        for entry_id in self.callback_counter_per_type[EntryType.RuntimePublishedValue]:
            rpv_maxval = max(rpv_maxval, self.callback_counter_per_type[EntryType.RuntimePublishedValue][entry_id])
            rpv_minval = min(rpv_minval, self.callback_counter_per_type[EntryType.RuntimePublishedValue][entry_id])

        # Round robin within groups
        self.assertLessEqual(var_maxval - var_minval, 1)
        self.assertLessEqual(rpv_maxval - rpv_minval, 1)

        # Difference between groups
        # Boundary condition may cause a group to have few entry to have 2 updates more than the other
        self.assertLessEqual(abs(rpv_maxval - var_maxval), 2)
        self.assertLessEqual(abs(rpv_minval - var_minval), 2)
        self.assertLessEqual(rpv_maxval - var_minval, 2)
        self.assertLessEqual(var_maxval - rpv_minval, 2)

    def respond_request(self, request: Request) -> Response:
        subfn = MemoryControl.Subfunction(request.subfn)
        if subfn == MemoryControl.Subfunction.Read:
            request_data = cast(protocol_typing.Request.MemoryControl.Read, self.protocol.parse_request(request))
            response_blocks: List[Tuple[int, bytes]] = []
            for block in request_data['blocks_to_read']:
                response_block = (block['address'], b'\x00' * block['length'])
                response_blocks.append(response_block)

            response = self.protocol.respond_read_memory_blocks(block_list=response_blocks)

        elif subfn == MemoryControl.Subfunction.ReadRPV:
            request_data = cast(protocol_typing.Request.MemoryControl.ReadRPV, self.protocol.parse_request(request))
            response_data = []
            for rpv_id in request_data['rpvs_id']:
                response_data.append((rpv_id, generate_random_value(EmbeddedDataType.float32)))
            response = self.protocol.respond_read_runtime_published_values(response_data)
        else:
            raise Exception('unknown subfunction')

        return response

    def update_callback(self, watcher: str, entry: DatastoreEntry):
        self.callback_counter_per_type[entry.get_type()][entry.get_id()] += 1

    def test_validate_round_robin(self):
        # This test reads lots of entry.
        # A limit is set on the response buffer size to ensure that not all entries can be round in a single request.
        # We validate that the round robin scheme works and alternate between RPV and Variables.

        rpv_entries = list(make_dummy_rpv_entries(start_id=0x1000, n=30, vartype=EmbeddedDataType.float32))
        var_entries = list(make_dummy_var_entries(address=0x2000, n=10, vartype=EmbeddedDataType.float32))
        var_entries += list(make_dummy_var_entries(address=0x3000, n=10, vartype=EmbeddedDataType.float32))
        var_entries += list(make_dummy_var_entries(address=0x4000, n=10, vartype=EmbeddedDataType.float32))

        self.datastore.add_entries(rpv_entries)
        self.datastore.add_entries(var_entries)
        dispatcher = RequestDispatcher()

        self.protocol.set_address_size_bits(32)

        all_rpvs: List[RuntimePublishedValue] = []
        for rpv_entry in rpv_entries:
            all_rpvs.append(rpv_entry.get_rpv())
        self.protocol.configure_rpvs(all_rpvs)

        for entry in self.datastore.get_all_entries():
            self.callback_counter_per_type[entry.get_type()][entry.get_id()] = 0

        reader = MemoryReader(self.protocol, dispatcher=dispatcher, datastore=self.datastore, request_priority=0)
        reader.set_max_request_payload_size(1024)
        reader.set_max_response_payload_size(20 * 4 + 4 * 2)
        reader.start()

        for entry in rpv_entries:
            self.datastore.start_watching(entry, 'unittest', value_change_callback=self.update_callback)

        for entry in var_entries:
            self.datastore.start_watching(entry, 'unittest', value_change_callback=self.update_callback)

        raw_read_data_container = self.CallbackDataContainer()
        raw_read_request_size = round(reader.max_response_payload_size * 1.5)    # we aim for 2 requests
        debug = False
        for i in range(50):
            if i == 20:

                reader.request_memory_read(0x10000, raw_read_request_size, callback=functools.partial(
                    self.raw_read_callback, container=raw_read_data_container))
            reader.process()
            dispatcher.process()
            req_record = dispatcher.pop_next()
            req_record.complete(success=True, response=self.respond_request(req_record.request))

            if debug:
                # Can be pasted
                for entry_id in self.callback_counter_per_type[EntryType.Var]:
                    n = self.callback_counter_per_type[EntryType.Var][entry_id]
                    print("Mem: 0x%04x - %d" % (self.datastore.get_entry(entry_id).get_address(), n))

                for entry_id in self.callback_counter_per_type[EntryType.RuntimePublishedValue]:
                    n = self.callback_counter_per_type[EntryType.RuntimePublishedValue][entry_id]
                    print("RPV: 0x%04x - %d" % (self.datastore.get_entry(entry_id).get_rpv().id, n))

            self.assert_round_robin()

        # Ake sure that our read has been executed in through all these requests
        self.assertEqual(raw_read_data_container.call_count, 1)
        self.assertTrue(raw_read_data_container.success, 1)
        self.assertEqual(len(raw_read_data_container.data), raw_read_request_size)


if __name__ == '__main__':
    import unittest
    unittest.main()
