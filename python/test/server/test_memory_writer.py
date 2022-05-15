import unittest

from scrutiny.server.datastore import Datastore, DatastoreEntry
from scrutiny.server.device.request_generator.memory_writer import MemoryWriter
from scrutiny.server.device.request_dispatcher import RequestDispatcher
from scrutiny.server.protocol import Protocol, Request, Response
from scrutiny.server.protocol.commands import *
from scrutiny.core.variable import *

from typing import List, Dict
from scrutiny.core.typehints import GenericCallback


def make_dummy_entries(address, n, vartype=VariableType.float32):
    for i in range(n):
        dummy_var = Variable('dummy', vartype=vartype, path_segments=['a', 'b', 'c'],
                             location=address + i * vartype.get_size_bit() // 8, endianness=Endianness.Little)
        entry = DatastoreEntry(DatastoreEntry.EntryType.Var, 'path_%d' % i, variable_def=dummy_var)
        yield entry


def d2f(d):
    return struct.unpack('f', struct.pack('f', d))[0]


class TestMemoryWriterBasicReadOperation(unittest.TestCase):

    def test_simple_write(self):
        nfloat = 1
        address = 0x1000
        ds = Datastore()
        entries = list(make_dummy_entries(address=address, n=nfloat, vartype=VariableType.float32))
        ds.add_entries(entries)
        dispatcher = RequestDispatcher()

        protocol = Protocol(1, 0)
        protocol.set_address_size_bits(32)
        writer = MemoryWriter(protocol, dispatcher=dispatcher, datastore=ds, request_priority=0)
        writer.set_max_request_size(1024)  # big enough for all of them
        writer.set_max_response_size(1024)  # big enough for all of them
        writer.start()

        for entry in entries:
            ds.start_watching(entry, 'unittest', GenericCallback(lambda *args, **kwargs: None))

        entry_to_write = entries[0]
        writer.process()
        dispatcher.process()
        self.assertIsNone(dispatcher.pop_next())
        entry_to_write.set_value(0)
        entry_to_write.update_target_value(d2f(3.1415926))
        self.assertTrue(entry_to_write.has_pending_target_update())
        writer.process()
        dispatcher.process()

        record = dispatcher.pop_next()
        self.assertIsNotNone(record)

        self.assertEqual(record.request.command, MemoryControl)
        self.assertEqual(MemoryControl.Subfunction(record.request.subfn), MemoryControl.Subfunction.Write)

        request_data = protocol.parse_request(record.request)
        self.assertTrue(request_data['valid'])

        self.assertEqual(len(request_data['blocks_to_write']), 1)
        self.assertEqual(request_data['blocks_to_write'][0]['address'], 0x1000)
        self.assertEqual(request_data['blocks_to_write'][0]['data'], struct.pack('<f', d2f(3.1415926)))
        
        block_in_response = []
        for block in request_data['blocks_to_write']:
            block_in_response.append( (block['address'], len(block['data'])) )

        response = protocol.respond_write_memory_blocks(block_in_response)

        record.complete(success=True, response=response)
        self.assertFalse(entry_to_write.has_pending_target_update())
