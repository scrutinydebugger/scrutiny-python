#    test_memory_writer.py
#        Test the bridge between the data store and the device memory (datastore to memory
#        direction only)
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import time

from scrutiny.server.datastore.datastore import Datastore
from scrutiny.server.datastore.datastore_entry import *
from scrutiny.server.datastore.entry_type import EntryType
from scrutiny.server.device.request_generator.memory_writer import MemoryWriter
from scrutiny.server.device.request_dispatcher import RequestDispatcher
from scrutiny.server.protocol import Protocol
from scrutiny.server.protocol.commands import *
import scrutiny.server.protocol.typing as protocol_typing
from scrutiny.core.basic_types import *
from scrutiny.core.variable import Variable
import struct
from test import ScrutinyUnitTest

from typing import List, Dict, Generator, cast
from scrutiny.core.typehints import GenericCallback


def make_dummy_var_entries(address, n, vartype=EmbeddedDataType.float32) -> Generator[DatastoreVariableEntry, None, None]:
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


class TestMemoryWriterBasicReadOperation(ScrutinyUnitTest):

    # Write a single datastore entry. Make sure the request is good.
    def test_simple_var_write(self):
        nfloat = 1
        address = 0x1000
        ds = Datastore()
        entries = list(make_dummy_var_entries(address=address, n=nfloat, vartype=EmbeddedDataType.float32))
        ds.add_entries(entries)
        dispatcher = RequestDispatcher()

        protocol = Protocol(1, 0)
        protocol.set_address_size_bits(32)
        writer = MemoryWriter(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        writer.set_max_request_payload_size(1024)  # big enough for all of them
        writer.set_max_response_payload_size(1024)  # big enough for all of them
        writer.start()

        for entry in entries:
            ds.start_watching(entry, 'unittest')

        entry_to_write = entries[0]
        writer.process()
        dispatcher.process()
        self.assertIsNone(dispatcher.pop_next())
        entry_to_write.set_value(0)
        update_request = entry_to_write.update_target_value(d2f(3.1415926))
        self.assertTrue(entry_to_write.has_pending_target_update())
        writer.process()
        dispatcher.process()

        record = dispatcher.pop_next()
        self.assertIsNotNone(record)

        self.assertEqual(record.request.command, MemoryControl)
        self.assertEqual(MemoryControl.Subfunction(record.request.subfn), MemoryControl.Subfunction.Write)

        request_data = cast(protocol_typing.Request.MemoryControl.Write, protocol.parse_request(record.request))

        self.assertEqual(len(request_data['blocks_to_write']), 1)
        self.assertEqual(request_data['blocks_to_write'][0]['address'], 0x1000)
        self.assertEqual(request_data['blocks_to_write'][0]['data'], struct.pack('<f', d2f(3.1415926)))

        block_in_response = []
        for block in request_data['blocks_to_write']:
            block_in_response.append((block['address'], len(block['data'])))

        response = protocol.respond_write_memory_blocks(block_in_response)

        record.complete(success=True, response=response)
        self.assertFalse(entry_to_write.has_pending_target_update())

        self.assertTrue(update_request.is_complete())
        self.assertTrue(update_request.is_success())

    def test_var_write_impossible_value(self):
        nfloat = 1
        address = 0x1000
        ds = Datastore()
        entries = list(make_dummy_var_entries(address=address, n=nfloat, vartype=EmbeddedDataType.float32))
        ds.add_entries(entries)
        dispatcher = RequestDispatcher()

        protocol = Protocol(1, 0)
        protocol.set_address_size_bits(32)
        writer = MemoryWriter(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        writer.start()

        for entry in entries:
            ds.start_watching(entry, 'unittest')

        entry_to_write = entries[0]
        writer.process()
        dispatcher.process()
        self.assertIsNone(dispatcher.pop_next())
        entry_to_write.set_value(0)
        update_request = entry_to_write.update_target_value("BAD VALUE")
        self.assertTrue(entry_to_write.has_pending_target_update())
        writer.process()
        dispatcher.process()

        record = dispatcher.pop_next()
        self.assertIsNone(record)
        self.assertFalse(entry_to_write.has_pending_target_update())

        self.assertTrue(update_request.is_complete())
        self.assertTrue(update_request.is_failed())

    # Update multiple entries. Make sure that all entries has been updated.

    def test_multiple_var_write(self):
        ndouble = 100
        address = 0x1000
        ds = Datastore()
        entries = list(make_dummy_var_entries(address=address, n=ndouble, vartype=EmbeddedDataType.float64))
        ds.add_entries(entries)
        dispatcher = RequestDispatcher()

        protocol = Protocol(1, 0)
        protocol.set_address_size_bits(32)
        writer = MemoryWriter(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        writer.set_max_request_payload_size(1024)  # Will require 4 request
        writer.set_max_response_payload_size(1024)  # big enough for all of them
        writer.start()

        for entry in entries:
            ds.start_watching(entry, 'unittest')

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
            self.assertEqual(MemoryControl.Subfunction(record.request.subfn), MemoryControl.Subfunction.Write, 'i=%d' % i)

            request_data = cast(protocol_typing.Request.MemoryControl.Write, protocol.parse_request(record.request))

            # Emulate the device response
            block_in_response = []
            for block in request_data['blocks_to_write']:
                block_in_response.append((block['address'], len(block['data'])))
                self.assertEqual(len(block['data']), 8)     # float64 = 8 bytes

            response = protocol.respond_write_memory_blocks(block_in_response)
            record.complete(success=True, response=response)    # This should trigger the datastore write callback

        # Make sure all entries has been updated. We check the update timestamp and the data itself
        for i in range(ndouble):
            self.assertFalse(entries[i].has_pending_target_update(), 'i=%d' % i)
            update_time = entries[i].get_last_target_update_timestamp()
            self.assertIsNotNone(update_time, 'i=%d' % i)
            self.assertGreaterEqual(update_time, time_start, 'i=%d' % i)

    def test_write_burst_do_all(self):
        # This test makes write request in burst (faster than memory writer can process them) and we
        # expect the memory writer to do them all in order and not skip any

        address = 0x1000
        ds = Datastore()
        entry = list(make_dummy_var_entries(address=address, n=1, vartype=EmbeddedDataType.float64))[0]
        ds.add_entry(entry)
        dispatcher = RequestDispatcher()

        protocol = Protocol(1, 0)
        protocol.set_address_size_bits(32)
        writer = MemoryWriter(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        writer.set_max_request_payload_size(1024)  # Will require 4 request
        writer.set_max_response_payload_size(1024)  # big enough for all of them
        writer.start()

        ds.start_watching(entry, 'unittest')

        # Initial check to make sure no request is pending
        writer.process()
        dispatcher.process()
        self.assertIsNone(dispatcher.pop_next())

        # Request a data write on  all data store entries
        entry.set_value(0)
        vals = [100, 200, 300]

        # We do burst writes. We expect the memory writer to do them all in order. No skip
        for val in vals:
            entry.update_target_value(val)

        time_start = time.time()
        time.sleep(0.010)
        for val in vals:
            writer.process()
            dispatcher.process()

            record = dispatcher.pop_next()
            self.assertIsNotNone(record, 'val=%d' % val)  # Make sure there is something to send

            self.assertEqual(record.request.command, MemoryControl, 'val=%d' % val)
            self.assertEqual(MemoryControl.Subfunction(record.request.subfn), MemoryControl.Subfunction.Write, 'val=%d' % val)

            request_data = cast(protocol_typing.Request.MemoryControl.Write, protocol.parse_request(record.request))

            # Emulate the device response
            block_in_response = []
            for block in request_data['blocks_to_write']:
                block_in_response.append((block['address'], len(block['data'])))
                self.assertEqual(len(block['data']), 8)     # float64 = 8 bytes

            response = protocol.respond_write_memory_blocks(block_in_response)
            record.complete(success=True, response=response)    # This should trigger the datastore write callback

            self.assertEqual(entry.get_value(), val)
            update_time = entry.get_last_target_update_timestamp()
            self.assertIsNotNone(update_time, 'val=%d' % val)
            self.assertGreaterEqual(update_time, time_start, 'val=%d' % val)

    # Write a single datastore entry. Make sure the request is good.

    def test_simple_rpv_write(self):
        nfloat = 1
        start_id = 0x1000
        ds = Datastore()
        entries = list(make_dummy_rpv_entries(start_id=start_id, n=nfloat, vartype=EmbeddedDataType.float32))
        ds.add_entries(entries)
        dispatcher = RequestDispatcher()

        protocol = Protocol(1, 0)
        protocol.configure_rpvs([entry.get_rpv() for entry in entries])
        writer = MemoryWriter(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        writer.set_max_request_payload_size(1024)  # big enough for all of them
        writer.set_max_response_payload_size(1024)  # big enough for all of them
        writer.start()

        for entry in entries:
            ds.start_watching(entry, 'unittest')

        entry_to_write = entries[0]
        writer.process()
        dispatcher.process()
        self.assertIsNone(dispatcher.pop_next())
        entry_to_write.set_value(0)
        update_request = entry_to_write.update_target_value(3.1415926)   # Will be converted to float32
        self.assertFalse(update_request.is_complete())
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

        self.assertTrue(update_request.is_complete())
        self.assertTrue(update_request.is_success())

    def test_rpv_write_impossible_value(self):
        nfloat = 1
        start_id = 0x1000
        ds = Datastore()
        entries = list(make_dummy_rpv_entries(start_id=start_id, n=nfloat, vartype=EmbeddedDataType.float32))
        ds.add_entries(entries)
        dispatcher = RequestDispatcher()

        protocol = Protocol(1, 0)
        protocol.configure_rpvs([entry.get_rpv() for entry in entries])
        writer = MemoryWriter(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        writer.start()

        for entry in entries:
            ds.start_watching(entry, 'unittest')

        entry_to_write = entries[0]
        writer.process()
        dispatcher.process()
        self.assertIsNone(dispatcher.pop_next())
        entry_to_write.set_value(0)
        update_request = entry_to_write.update_target_value("BAD VALUE")   # Will be converted to float32
        self.assertFalse(update_request.is_complete())
        self.assertTrue(entry_to_write.has_pending_target_update())
        writer.process()
        dispatcher.process()

        record = dispatcher.pop_next()
        self.assertIsNone(record)
        self.assertFalse(entry_to_write.has_pending_target_update())

        self.assertTrue(update_request.is_complete())
        self.assertTrue(update_request.is_failed())

    def test_multiple_rpv_write(self):
        ndouble = 100
        start_id = 0x1000
        ds = Datastore()
        entries = list(make_dummy_rpv_entries(start_id=start_id, n=ndouble, vartype=EmbeddedDataType.float64))
        ds.add_entries(entries)
        dispatcher = RequestDispatcher()

        protocol = Protocol(1, 0)
        protocol.configure_rpvs([entry.get_rpv() for entry in entries])
        writer = MemoryWriter(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        writer.set_max_request_payload_size(1024)  # Will require 4 request minimum
        writer.set_max_response_payload_size(1024)  # big enough for all of them
        writer.start()

        for entry in entries:
            ds.start_watching(entry, 'unittest')

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
            update_time = entries[i].get_last_target_update_timestamp()
            self.assertIsNotNone(update_time, 'i=%d' % i)
            self.assertGreaterEqual(update_time, time_start, 'i=%d' % i)
            self.assertEqual(entries[i].get_value(), i)

    def test_multiple_mixed_write(self):
        ds = Datastore()
        rpv_entries = list(make_dummy_rpv_entries(start_id=0x1000, n=5, vartype=EmbeddedDataType.float64))
        var_entries = list(make_dummy_var_entries(address=0x2000, n=5, vartype=EmbeddedDataType.float32))
        all_entries = rpv_entries + var_entries
        ds.add_entries(all_entries)
        dispatcher = RequestDispatcher()

        protocol = Protocol(1, 0)
        protocol.configure_rpvs([entry.get_rpv() for entry in rpv_entries])
        writer = MemoryWriter(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        writer.set_max_request_payload_size(1024)  # Will require 4 request minimum
        writer.set_max_response_payload_size(1024)  # big enough for all of them
        writer.start()

        for entry in all_entries:
            ds.start_watching(entry, 'unittest')

        # Initial check to make sure no request is pending
        writer.process()
        dispatcher.process()
        self.assertIsNone(dispatcher.pop_next())

        # Request a data write on  all data store entries
        value_dict = {}
        for i in range(len(all_entries)):
            val = i + 10
            all_entries[i].set_value(0)
            all_entries[i].update_target_value(val)
            value_dict[all_entries[i].get_id()] = val

        for entry in all_entries:
            self.assertTrue(entry.has_pending_target_update())  # Make sure the write request is there

        time_start = time.time()

        # Memory writer writes one entry per request. it's a choice
        for i in range(len(all_entries)):
            writer.process()
            dispatcher.process()

            record = dispatcher.pop_next()
            self.assertIsNotNone(record, 'i=%d' % i)  # Make sure there is something to send

            self.assertEqual(record.request.command, MemoryControl, 'i=%d' % i)
            subfn = MemoryControl.Subfunction(record.request.subfn)
            request_data = protocol.parse_request(record.request)
            if subfn == MemoryControl.Subfunction.WriteRPV:
                request_data = cast(protocol_typing.Request.MemoryControl.WriteRPV, request_data)
                response = protocol.respond_write_runtime_published_values([rpv['id'] for rpv in request_data['rpvs']])  # Emulate the device response
            elif subfn == MemoryControl.Subfunction.Write:
                request_data = cast(protocol_typing.Request.MemoryControl.Write, request_data)
                # Emulate the device response
                block_in_response = []
                for block in request_data['blocks_to_write']:
                    block_in_response.append((block['address'], len(block['data'])))
                    self.assertEqual(len(block['data']), 4)     # float32 = 8 bytes
                response = protocol.respond_write_memory_blocks(block_in_response)
            else:
                raise Exception('Bad subfunction')
            record.complete(success=True, response=response)    # This should trigger the datastore write callback

        # Make sure all entries has been updated. We check the update timestamp and the data itself
        for i in range(len(all_entries)):
            self.assertFalse(all_entries[i].has_pending_target_update(), 'i=%d' % i)
            update_time = all_entries[i].get_last_target_update_timestamp()
            self.assertIsNotNone(update_time, 'i=%d' % i)
            self.assertGreaterEqual(update_time, time_start, 'i=%d' % i)
            self.assertEqual(all_entries[i].get_value(), value_dict[all_entries[i].get_id()])
