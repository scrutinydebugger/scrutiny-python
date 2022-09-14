import unittest
import time
import random

from scrutiny.server.datastore import *
from scrutiny.server.device.request_generator.rpv_writer import RPVWriter
from scrutiny.server.device.request_dispatcher import RequestDispatcher
from scrutiny.server.protocol import Protocol
import scrutiny.server.protocol.typing as protocol_typing
from scrutiny.server.protocol.commands import *
from scrutiny.core.basic_types import *
from scrutiny.core.variable import *
import struct

from typing import cast, Generator
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


class TestRPVWriter(unittest.TestCase):

    # Write a single datastore entry. Make sure the request is good.
    def test_simple_write(self):
        nfloat = 1
        start_id = 0x1000
        ds = Datastore()
        entries = list(make_dummy_entries(start_id=start_id, n=nfloat, vartype=EmbeddedDataType.float32))
        ds.add_entries(entries)
        dispatcher = RequestDispatcher()

        protocol = Protocol(1, 0)
        protocol.configure_rpvs([entry.get_rpv() for entry in entries])
        writer = RPVWriter(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        writer.set_max_request_payload_size(1024)  # big enough for all of them
        writer.set_max_response_payload_size(1024)  # big enough for all of them
        writer.start()

        for entry in entries:
            ds.start_watching(entry, 'unittest', GenericCallback(lambda *args, **kwargs: None))

        entry_to_write = entries[0]
        writer.process()
        dispatcher.process()
        self.assertIsNone(dispatcher.pop_next())
        entry_to_write.set_value(0)
        entry_to_write.update_target_value(3.1415926)   # Will be converted to float32
        self.assertTrue(entry_to_write.has_pending_target_update())
        writer.process()
        dispatcher.process()

        record = dispatcher.pop_next()
        self.assertIsNotNone(record)

        self.assertEqual(record.request.command, MemoryControl)
        self.assertEqual(MemoryControl.Subfunction(record.request.subfn), MemoryControl.Subfunction.WriteRPV)

        request_data = cast(protocol_typing.Request.MemoryControl.WriteRPV, protocol.parse_request(record.request))

        self.assertEqual(len(request_data['rpvs']), 1)
        self.assertEqual(request_data['rpvs'][0]['id'], 0x1000)
        self.assertEqual(request_data['rpvs'][0]['value'], d2f(3.1415926))  # Needs to use float32 representation.

        # Make the RpVReader happy by responding.
        response = protocol.respond_write_runtime_published_values([rpv['id'] for rpv in request_data['rpvs']]) 

        record.complete(success=True, response=response)
        self.assertFalse(entry_to_write.has_pending_target_update())

    def test_multiple_write(self):
        ndouble = 100
        start_id = 0x1000
        ds = Datastore()
        entries = list(make_dummy_entries(start_id=start_id, n=ndouble, vartype=EmbeddedDataType.float64))
        ds.add_entries(entries)
        dispatcher = RequestDispatcher()

        protocol = Protocol(1, 0)
        protocol.configure_rpvs([entry.get_rpv() for entry in entries])
        writer = RPVWriter(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        writer.set_max_request_payload_size(1024)  # Will require 4 request minimum
        writer.set_max_response_payload_size(1024)  # big enough for all of them
        writer.start()

        for entry in entries:
            ds.start_watching(entry, 'unittest', GenericCallback(lambda *args, **kwargs: None))

        # Initial check to make sure no request is pending
        writer.process()
        dispatcher.process()
        self.assertIsNone(dispatcher.pop_next())

        # Request a data write on  all data store entries
        for i in range(ndouble):
            entries[i].set_value(0)
            entries[i].update_target_value(i)

        for entry in entries:
            self.assertTrue(entry.has_pending_target_update())  # Make sure the write request is there

        time_start = time.time()

        # Memory writer writes one entry per request. it's a choice
        for i in range(ndouble):
            writer.process()
            dispatcher.process()

            record = dispatcher.pop_next()
            self.assertIsNotNone(record, 'i=%d' % i)  # Make sure there is something to send

            self.assertEqual(record.request.command, MemoryControl, 'i=%d' % i)
            self.assertEqual(MemoryControl.Subfunction(record.request.subfn), MemoryControl.Subfunction.WriteRPV, 'i=%d' % i)

            request_data = cast(protocol_typing.Request.MemoryControl.WriteRPV, protocol.parse_request(record.request))

            # Emulate the device response
            response = protocol.respond_write_runtime_published_values([rpv['id'] for rpv in request_data['rpvs']]) 
            record.complete(success=True, response=response)    # This should trigger the datastore write callback

        # Make sure all entries has been updated. We check the update timestamp and the data itself
        for i in range(ndouble):
            self.assertFalse(entries[i].has_pending_target_update(), 'i=%d' % i)
            update_time = entries[i].get_last_update_timestamp()
            self.assertIsNotNone(update_time, 'i=%d' % i)
            self.assertGreaterEqual(update_time, time_start, 'i=%d' % i)
            self.assertEqual(entries[i].get_value(), i)
