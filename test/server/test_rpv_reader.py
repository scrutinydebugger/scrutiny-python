import unittest
import random
from dataclasses import dataclass
from sortedcontainers import SortedSet

from scrutiny.server.datastore import Datastore, DatastoreRPVEntry
from scrutiny.server.device.request_generator.rpv_reader import RPVReader, DataStoreEntrySortableByRpvId
from scrutiny.server.device.request_dispatcher import RequestDispatcher
from scrutiny.server.protocol import Protocol,  Response
from scrutiny.server.protocol.commands import *
from scrutiny.core.variable import *
from scrutiny.core.basic_types import *
import scrutiny.server.protocol.typing as protocol_typing

from typing import List, Dict, cast, Generator
from scrutiny.core.typehints import GenericCallback

def generate_random_value(datatype: EmbeddedDataType) -> Encodable:
    # Generate random bitstring of the right size. Then decode it.
    codec = Codecs.get(datatype, Endianness.Big)
    if datatype in [EmbeddedDataType.float8, EmbeddedDataType.float16, EmbeddedDataType.float32, EmbeddedDataType.float64, EmbeddedDataType.float128, EmbeddedDataType.float256]:
        return codec.decode(codec.encode((random.random()-0.5)*1000))

    bytestr = bytes([random.randint(0, 0xff) for i in range(datatype.get_size_byte())])
    return codec.decode(bytestr)


def make_dummy_entries(start_id, n, vartype=EmbeddedDataType.float32) -> Generator[DatastoreRPVEntry, None, None]:
    for i in range(n):
        rpv = RuntimePublishedValue(id=start_id+i, datatype=vartype)
        entry = DatastoreRPVEntry('rpv_%d' % i, rpv=rpv)
        yield entry


def d2f(d):
    return struct.unpack('f', struct.pack('f', d))[0]


class TestRPVReaderBasicReadOperation(unittest.TestCase):
    # Make sure that the entries are sortable by ID with the thirdparty SortedSet object

    def test_sorted_set(self):
        theset = SortedSet()
        entries = list(make_dummy_entries(1000, 5))
        entries += list(make_dummy_entries(0, 5))
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

    def generic_test_read_rpv_sequence(self, expected_rpv_entry_sequence:List[List[DatastoreRPVEntry]], reader:RPVReader, dispatcher:RequestDispatcher, protocol:Protocol, niter:int=5):
        all_rpvs:List[RuntimePublishedValue] = []
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

                response = protocol.respond_read_runtime_published_values(vals = expected_rpv_values)
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
        entries = list(make_dummy_entries(start_id=start_id, n=nfloat, vartype=EmbeddedDataType.float32))
        ds.add_entries(entries)
        dispatcher = RequestDispatcher()

        protocol = Protocol(1, 0)
        protocol.set_address_size_bits(32)
        reader = RPVReader(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        reader.set_max_request_payload_size(1024)  # big enough for all of them
        reader.set_max_response_payload_size(1024)  # big enough for all of them
        reader.start()

        for entry in entries:
            ds.start_watching(entry, 'unittest', GenericCallback(lambda *args, **kwargs: None))

        expected_rpv_sequence = [
            entries
        ]

        self.generic_test_read_rpv_sequence(expected_rpv_sequence, reader, dispatcher, protocol, niter=5)

    def test_read_request_multiple_rpvs_2rpvs_per_req(self):
        # Here, we define 3 rpvs and impose a limit on the request size to allow only 2 rpv read per request.
        # We make sure that blocks are completely read.


        start_id = 0x1000
        ds = Datastore()
        entries = list(make_dummy_entries(start_id=start_id, n=3, vartype=EmbeddedDataType.float32))

        ds.add_entries(entries)
        dispatcher = RequestDispatcher()
        protocol = Protocol(1, 0)
        reader = RPVReader(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        reader.set_max_request_payload_size(protocol.read_rpv_request_size_per_rpv() * 2)  # 2 rpv per request
        reader.set_max_response_payload_size(1024)  # Non-limiting here
        reader.start()

        for entry in entries:
            ds.start_watching(entry, 'unittest', GenericCallback(lambda *args, **kwargs: None))

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
        entries:List[DatastoreRPVEntry] = []
        entries += list(make_dummy_entries(start_id=100, n=nfloat, vartype=EmbeddedDataType.float32))

        ds = Datastore()
        ds.add_entries(entries)

        dispatcher = RequestDispatcher()
        protocol = Protocol(1, 0)
        reader = RPVReader(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        reader.set_max_request_payload_size(1024)  # Non-limiting here
        temp_list = [entry.get_rpv() for entry in entries]
        reader.set_max_response_payload_size(protocol.read_rpv_response_required_size(temp_list[0:number_per_req]) )    # All RPV are the same type,s o we can do that
        reader.start()

        for entry in entries:
            ds.start_watching(entry, 'unittest', GenericCallback(lambda *args, **kwargs: None))

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

        entries:List[DatastoreRPVEntry] = []
        for i in range(20):  # different variable size
            entries += list(make_dummy_entries(start_id=i * 0x100 + 0, n=1, vartype=EmbeddedDataType.uint64))
            entries += list(make_dummy_entries(start_id=i * 0x100 + 1, n=1, vartype=EmbeddedDataType.uint32))
            entries += list(make_dummy_entries(start_id=i * 0x100 + 2, n=1, vartype=EmbeddedDataType.uint16))
            entries += list(make_dummy_entries(start_id=i * 0x100 + 3, n=1, vartype=EmbeddedDataType.uint8))

        # Setup everything
        ds = Datastore()
        ds.add_entries(entries)
        dispatcher = RequestDispatcher()
        protocol = Protocol(1, 0)
        protocol.configure_rpvs([entry.get_rpv() for entry in entries])
        reader = RPVReader(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        reader.set_max_request_payload_size(1024)
        reader.set_max_response_payload_size(1024)
        reader.start()

        # We need to watch the variable so that they are read
        for entry in entries:
            ds.start_watching(entry, 'unittest', callback=GenericCallback(lambda *args, **kwargs: None))

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
                response_vals:List[Tuple[int, Encodable]] = []
                for rpv_id in request_data['rpvs_id']:
                    response_vals.append( (rpv_id, int(random.random()*255)) )

                response = protocol.respond_read_runtime_published_values(response_vals)  # Make device hadnler happy so we can continue the test
                record.complete(success=True, response=response)

    def test_response_size_limit(self):
        # Make sure the maximum response size is always respected

        entries:List[DatastoreRPVEntry] = []
        for i in range(20):  # different variable size
            entries += list(make_dummy_entries(start_id=i * 0x100 + 0, n=1, vartype=EmbeddedDataType.uint64))
            entries += list(make_dummy_entries(start_id=i * 0x100 + 1, n=1, vartype=EmbeddedDataType.uint32))
            entries += list(make_dummy_entries(start_id=i * 0x100 + 2, n=1, vartype=EmbeddedDataType.uint16))
            entries += list(make_dummy_entries(start_id=i * 0x100 + 3, n=1, vartype=EmbeddedDataType.uint8))

        # Setup everything
        ds = Datastore()
        ds.add_entries(entries)
        dispatcher = RequestDispatcher()
        protocol = Protocol(1, 0)
        protocol.configure_rpvs([entry.get_rpv() for entry in entries])
        reader = RPVReader(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        reader.set_max_request_payload_size(1024)
        reader.set_max_response_payload_size(1024)
        reader.start()

        for entry in entries:
            ds.start_watching(entry, 'unittest', callback=GenericCallback(lambda *args, **kwargs: None))

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
                response_vals:List[Tuple[int, Encodable]] = []
                for rpv_id in request_data['rpvs_id']:
                    response_vals.append( (rpv_id, int(random.random()*255)) )

                response = protocol.respond_read_runtime_published_values(response_vals)
                self.assertLessEqual(response.data_size(), max_response_payload_size)    # That's the main test
                record.complete(success=True, response=response)
