#    test_memory_writer.py
#        Test the bridge between the data store and the device memory (datastore to memory
#        direction only)
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import time

from scrutiny.server.datastore.datastore import Datastore
from scrutiny.server.datastore.datastore_entry import *
from scrutiny.server.device.submodules.memory_writer import MemoryWriter
from scrutiny.server.device.request_dispatcher import RequestDispatcher
from scrutiny.server.protocol import Protocol, Response

from scrutiny.server.protocol.commands import *
import scrutiny.server.protocol.typing as protocol_typing
from scrutiny.core.basic_types import *
from scrutiny.core.variable import Variable
import struct
from test import ScrutinyUnitTest
from dataclasses import dataclass
import random
import functools
import math
from typing import List, Generator, cast, Optional


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


no_callback:UpdateTargetRequestCallback = lambda *args, **kwargs: None

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

        entry_to_write = entries[0]
        writer.process()
        dispatcher.process()
        self.assertIsNone(dispatcher.pop_next())
        entry_to_write.set_value(0)
        update_request = ds.update_target_value(entry_to_write, d2f(3.1415926), no_callback)
        self.assertTrue(ds.has_pending_target_update())
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
        self.assertFalse(ds.has_pending_target_update())

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

        entry_to_write = entries[0]
        writer.process()
        dispatcher.process()
        self.assertIsNone(dispatcher.pop_next())
        entry_to_write.set_value(0)
        update_request = ds.update_target_value(entry_to_write, "BAD VALUE", no_callback)
        self.assertTrue(ds.has_pending_target_update())
        writer.process()
        dispatcher.process()

        record = dispatcher.pop_next()
        self.assertIsNone(record)
        self.assertFalse(ds.has_pending_target_update())

        self.assertTrue(update_request.is_complete())
        self.assertTrue(update_request.is_failed())

    def test_write_readonly(self):
        ds = Datastore()
        ds.add_entries(list(make_dummy_var_entries(address=1000, n=1, vartype=EmbeddedDataType.float32)))
        ds.add_entries(list(make_dummy_var_entries(address=2000, n=1, vartype=EmbeddedDataType.float32)))
        ds.add_entries(list(make_dummy_var_entries(address=3000, n=1, vartype=EmbeddedDataType.float32)))
        ds.add_entries(list(make_dummy_var_entries(address=4000, n=1, vartype=EmbeddedDataType.float32)))
        entries = cast(List[DatastoreVariableEntry], list(ds.get_all_entries()))
        entries.sort(key=lambda x: x.get_address())

        regions = [
            (990, 10),
            (1990, 11),
            (3003, 1),
            (4004, 10)
        ]

        allowed_write = [True, False, False, True]

        dispatcher = RequestDispatcher()
        protocol = Protocol(1, 0)
        protocol.set_address_size_bits(32)
        writer = MemoryWriter(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        for region in regions:
            writer.add_readonly_region(start_addr=region[0], size=region[1])
        writer.start()

        for i in range(4):
            entry_to_write = entries[i]
            writer.process()
            dispatcher.process()
            self.assertIsNone(dispatcher.pop_next())
            entry_to_write.set_value(0)
            update_request = ds.update_target_value(entry_to_write, d2f(3.1415926), no_callback)
            self.assertTrue(ds.has_pending_target_update())
            writer.process()
            dispatcher.process()

            record = dispatcher.pop_next()
            if allowed_write[i]:
                self.assertIsNotNone(record)

                request_data = cast(protocol_typing.Request.MemoryControl.Write, protocol.parse_request(record.request))
                block_in_response = []
                for block in request_data['blocks_to_write']:
                    block_in_response.append((block['address'], len(block['data'])))

                response = protocol.respond_write_memory_blocks(block_in_response)

                record.complete(True, response)
                self.assertFalse(ds.has_pending_target_update())
                self.assertTrue(update_request.is_complete())
                self.assertTrue(update_request.is_success())
            else:
                self.assertIsNone(record)
                self.assertFalse(ds.has_pending_target_update())
                self.assertTrue(update_request.is_complete())
                self.assertFalse(update_request.is_success())

    def test_write_forbidden(self):
        ds = Datastore()
        ds.add_entries(list(make_dummy_var_entries(address=1000, n=1, vartype=EmbeddedDataType.float32)))
        ds.add_entries(list(make_dummy_var_entries(address=2000, n=1, vartype=EmbeddedDataType.float32)))
        ds.add_entries(list(make_dummy_var_entries(address=3000, n=1, vartype=EmbeddedDataType.float32)))
        ds.add_entries(list(make_dummy_var_entries(address=4000, n=1, vartype=EmbeddedDataType.float32)))
        entries = cast(List[DatastoreVariableEntry], list(ds.get_all_entries()))
        entries.sort(key=lambda x: x.get_address())

        regions = [
            (990, 10),
            (1990, 11),
            (3003, 1),
            (4004, 10)
        ]

        allowed_write = [True, False, False, True]

        dispatcher = RequestDispatcher()
        protocol = Protocol(1, 0)
        protocol.set_address_size_bits(32)
        writer = MemoryWriter(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        for region in regions:
            writer.add_forbidden_region(start_addr=region[0], size=region[1])
        writer.start()

        for i in range(4):
            entry_to_write = entries[i]
            writer.process()
            dispatcher.process()
            self.assertIsNone(dispatcher.pop_next())
            entry_to_write.set_value(0)
            update_request = ds.update_target_value(entry_to_write, d2f(3.1415926), no_callback)
            self.assertTrue(ds.has_pending_target_update())
            writer.process()
            dispatcher.process()

            record = dispatcher.pop_next()
            if allowed_write[i]:
                self.assertIsNotNone(record)

                request_data = cast(protocol_typing.Request.MemoryControl.Write, protocol.parse_request(record.request))
                block_in_response = []
                for block in request_data['blocks_to_write']:
                    block_in_response.append((block['address'], len(block['data'])))

                response = protocol.respond_write_memory_blocks(block_in_response)

                record.complete(True, response)
                self.assertFalse(ds.has_pending_target_update())
                self.assertTrue(update_request.is_complete())
                self.assertTrue(update_request.is_success())
            else:
                self.assertIsNone(record)
                self.assertFalse(ds.has_pending_target_update())
                self.assertTrue(update_request.is_complete())
                self.assertFalse(update_request.is_success())

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

        # Initial check to make sure no request is pending
        writer.process()
        dispatcher.process()
        self.assertIsNone(dispatcher.pop_next())

        # Request a data write on  all data store entries
        for i in range(ndouble):
            entries[i].set_value(0)
            ds.update_target_value(entries[i], i, no_callback)

        self.assertEqual(ds.get_pending_target_update_count(), len(entries))  # Make sure the write request are there

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
        self.assertFalse(ds.has_pending_target_update())
        for i in range(ndouble):
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

        # Initial check to make sure no request is pending
        writer.process()
        dispatcher.process()
        self.assertIsNone(dispatcher.pop_next())

        # Request a data write on  all data store entries
        entry.set_value(0)
        vals = [100, 200, 300]

        # We do burst writes. We expect the memory writer to do them all in order. No skip
        for val in vals:
            ds.update_target_value(entry, val, no_callback)

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

        entry_to_write = entries[0]
        writer.process()
        dispatcher.process()
        self.assertIsNone(dispatcher.pop_next())
        entry_to_write.set_value(0)
        update_request = ds.update_target_value(entry_to_write, 3.1415926, no_callback)   # Will be converted to float32
        self.assertFalse(update_request.is_complete())
        self.assertTrue(ds.has_pending_target_update())
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
        self.assertFalse(ds.has_pending_target_update())

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

        entry_to_write = entries[0]
        writer.process()
        dispatcher.process()
        self.assertIsNone(dispatcher.pop_next())
        entry_to_write.set_value(0)
        update_request = ds.update_target_value(entry_to_write, "BAD VALUE", no_callback)   # Will be converted to float32
        self.assertFalse(update_request.is_complete())
        self.assertTrue(ds.has_pending_target_update())
        writer.process()
        dispatcher.process()

        record = dispatcher.pop_next()
        self.assertIsNone(record)
        self.assertFalse(ds.has_pending_target_update())

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

        # Initial check to make sure no request is pending
        writer.process()
        dispatcher.process()
        self.assertIsNone(dispatcher.pop_next())

        # Request a data write on  all data store entries
        for i in range(ndouble):
            entries[i].set_value(0)
            ds.update_target_value(entries[i], i, no_callback)

        self.assertEqual(ds.get_pending_target_update_count(), len(entries))  # Make sure the write request are there

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
        self.assertFalse(ds.has_pending_target_update())
        for i in range(ndouble):
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
            ds.update_target_value(all_entries[i], val, no_callback)
            value_dict[all_entries[i].get_id()] = val

        self.assertEqual(ds.get_pending_target_update_count(), len(all_entries))  # Make sure the write request are there

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
        self.assertFalse(ds.has_pending_target_update())
        for i in range(len(all_entries)):
            update_time = all_entries[i].get_last_target_update_timestamp()
            self.assertIsNotNone(update_time, 'i=%d' % i)
            self.assertGreaterEqual(update_time, time_start, 'i=%d' % i)
            self.assertEqual(all_entries[i].get_value(), value_dict[all_entries[i].get_id()])


class TestRawMemoryWrite(ScrutinyUnitTest):
    @dataclass
    class CallbackDataContainer:
        call_count: int = 0
        success: Optional[bool] = None
        error: Optional[str] = None

    def the_callback(self, request, success, error, container: CallbackDataContainer):
        container.call_count += 1
        container.success = success
        container.error = error

    def setUp(self):
        self.ds = Datastore()
        self.dispatcher = RequestDispatcher()
        self.protocol = Protocol(1, 0)
        self.writer = MemoryWriter(protocol=self.protocol, dispatcher=self.dispatcher, datastore=self.ds, request_priority=0)
        self.writer.set_max_request_payload_size(128)
        self.writer.set_max_response_payload_size(256)
        self.writer.start()

    def test_simple_write(self):
        for i in range(3):
            self.writer.process()
        self.assertIsNone(self.dispatcher.pop_next())

        payload = bytes([random.randint(0, 255) for i in range(257)])

        callback_data = self.CallbackDataContainer()
        self.writer.request_memory_write(0x1000, payload, callback=functools.partial(self.the_callback, container=callback_data))

        for i in range(3):
            cursor = i * 128

            self.writer.process()
            record = self.dispatcher.pop_next()
            self.assertIsNotNone(record)
            self.assertEqual(record.request.command, MemoryControl)
            self.assertEqual(MemoryControl.Subfunction(record.request.subfn), MemoryControl.Subfunction.Write)
            request_data = cast(protocol_typing.Request.MemoryControl.Write, self.protocol.parse_request(record.request))
            self.assertEqual(len(request_data['blocks_to_write']), 1)
            self.assertEqual(request_data['blocks_to_write'][0]['address'], 0x1000 + cursor)
            self.assertEqual(request_data['blocks_to_write'][0]['data'], payload[cursor:cursor + 128])
            response = self.protocol.respond_write_memory_blocks([(0x1000 + cursor, len(payload[cursor:cursor + 128]))])
            record.complete(True, response)

            if i < 2:
                self.assertEqual(callback_data.call_count, 0)
            else:
                self.assertEqual(callback_data.call_count, 1)
                self.assertTrue(callback_data.success)
                self.assertIsNotNone(callback_data.error)

    def test_write_failure(self):
        for i in range(3):
            self.writer.process()
        self.assertIsNone(self.dispatcher.pop_next())

        callback_data = self.CallbackDataContainer()
        payload = bytes([random.randint(0, 255) for i in range(257)])
        self.writer.request_memory_write(0x1000, payload, callback=functools.partial(self.the_callback, container=callback_data))

        for i in range(2):
            cursor = i * 128

            self.writer.process()
            record = self.dispatcher.pop_next()
            self.assertIsNotNone(record)
            self.assertEqual(record.request.command, MemoryControl)
            self.assertEqual(MemoryControl.Subfunction(record.request.subfn), MemoryControl.Subfunction.Write)
            request_data = cast(protocol_typing.Request.MemoryControl.Read, self.protocol.parse_request(record.request))
            self.assertEqual(len(request_data['blocks_to_write']), 1)
            self.assertEqual(request_data['blocks_to_write'][0]['address'], 0x1000 + cursor)
            self.assertEqual(request_data['blocks_to_write'][0]['data'], payload[cursor:cursor + 128])
            response = self.protocol.respond_write_memory_blocks([(0x1000 + cursor, len(payload[cursor:cursor + 128]))])

            if i == 0:
                record.complete(True, response)
                self.assertEqual(callback_data.call_count, 0)
            else:
                record.complete(False)
                self.assertEqual(callback_data.call_count, 1)
                self.assertFalse(callback_data.success)     # Failure detection
                self.assertIsNotNone(callback_data.error)
                self.assertGreater(len(callback_data.error), 0)

    def test_write_failure_by_nack(self):
        for i in range(3):
            self.writer.process()
        self.assertIsNone(self.dispatcher.pop_next())

        callback_data = self.CallbackDataContainer()
        payload = bytes([random.randint(0, 255) for i in range(257)])
        self.writer.request_memory_write(0x1000, payload, callback=functools.partial(self.the_callback, container=callback_data))

        for i in range(2):
            cursor = i * 128

            self.writer.process()
            record = self.dispatcher.pop_next()
            self.assertIsNotNone(record)
            self.assertEqual(record.request.command, MemoryControl)
            self.assertEqual(MemoryControl.Subfunction(record.request.subfn), MemoryControl.Subfunction.Write)
            request_data = cast(protocol_typing.Request.MemoryControl.Read, self.protocol.parse_request(record.request))
            self.assertEqual(len(request_data['blocks_to_write']), 1)
            self.assertEqual(request_data['blocks_to_write'][0]['address'], 0x1000 + cursor)
            self.assertEqual(request_data['blocks_to_write'][0]['data'], payload[cursor:cursor + 128])

            if i == 0:
                response = self.protocol.respond_write_memory_blocks([(0x1000 + cursor, len(payload[cursor:cursor + 128]))])
                record.complete(True, response)
                self.assertEqual(callback_data.call_count, 0)
            else:
                response = Response(record.request.command, record.request.subfn, Response.ResponseCode.FailureToProceed)
                record.complete(True, response)
                self.assertEqual(callback_data.call_count, 1)
                self.assertFalse(callback_data.success)     # Failure detection
                self.assertIsNotNone(callback_data.error)
                self.assertGreater(len(callback_data.error), 0)

    def test_write_readonly_early_fail(self):
        for i in range(3):
            self.writer.process()
        self.assertIsNone(self.dispatcher.pop_next())

        callback_data = self.CallbackDataContainer()
        self.writer.add_readonly_region(0x1000 - 10, 11)

        payload = bytes([random.randint(0, 255) for i in range(257)])
        self.writer.request_memory_write(0x1000, payload, callback=functools.partial(self.the_callback, container=callback_data))
        self.assertEqual(callback_data.call_count, 0)
        self.writer.process()
        self.assertEqual(callback_data.call_count, 1)
        self.assertFalse(callback_data.success)     # Failure detection
        self.assertIsNotNone(callback_data.error)
        self.assertGreater(len(callback_data.error), 0)

    def test_write_forbidden_early_fail(self):
        for i in range(3):
            self.writer.process()
        self.assertIsNone(self.dispatcher.pop_next())

        callback_data = self.CallbackDataContainer()
        self.writer.add_forbidden_region(0x1000 - 10, 11)

        payload = bytes([random.randint(0, 255) for i in range(257)])
        self.writer.request_memory_write(0x1000, payload, callback=functools.partial(self.the_callback, container=callback_data))
        self.assertEqual(callback_data.call_count, 0)
        self.writer.process()
        self.assertEqual(callback_data.call_count, 1)
        self.assertFalse(callback_data.success)     # Failure detection
        self.assertIsNotNone(callback_data.error)
        self.assertGreater(len(callback_data.error), 0)

    def test_write_multiple_blocks(self):
        max_request_size = 128
        for i in range(3):
            self.writer.process()
        self.assertIsNone(self.dispatcher.pop_next())

        payload1 = bytes([random.randint(0, 255) for i in range(257)])
        payload2 = bytes([random.randint(0, 255) for i in range(125)])
        payload3 = bytes([random.randint(0, 255) for i in range(400)])

        callback_data = self.CallbackDataContainer()
        self.writer.request_memory_write(0x1000, payload1, callback=functools.partial(self.the_callback, container=callback_data))
        self.writer.request_memory_write(0x2000, payload2, callback=functools.partial(self.the_callback, container=callback_data))
        self.writer.request_memory_write(0x3000, payload3, callback=functools.partial(self.the_callback, container=callback_data))

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

            nchunk = math.ceil(len(payload) / max_request_size)
            for i in range(nchunk):
                cursor = i * max_request_size

                self.writer.process()
                record = self.dispatcher.pop_next()
                self.assertIsNotNone(record)
                self.assertEqual(record.request.command, MemoryControl)
                self.assertEqual(MemoryControl.Subfunction(record.request.subfn), MemoryControl.Subfunction.Write)
                request_data = cast(protocol_typing.Request.MemoryControl.Write, self.protocol.parse_request(record.request))
                self.assertEqual(len(request_data['blocks_to_write']), 1)
                self.assertEqual(request_data['blocks_to_write'][0]['address'], address + cursor)
                self.assertEqual(request_data['blocks_to_write'][0]['data'], payload[cursor:cursor + max_request_size])
                response = self.protocol.respond_write_memory_blocks([(address + cursor, len(payload[cursor:cursor + max_request_size]))])
                record.complete(True, response)
                if i < nchunk - 1:
                    self.assertEqual(callback_data.call_count, msg)
                else:
                    self.assertEqual(callback_data.call_count, msg + 1)
                    self.assertTrue(callback_data.success)
                    self.assertIsNotNone(callback_data.error)


if __name__ == '__main__':
    import unittest
    unittest.main()
