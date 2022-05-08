#    test_datastore_updater.py
#        Test the Datastore Updater capability to generate requests based on variable subscription
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import unittest

from scrutiny.server.datastore import Datastore, DatastoreEntry
from scrutiny.server.device.request_generator.datastore_updater import DatastoreUpdater
from scrutiny.server.device.request_dispatcher import RequestDispatcher
from scrutiny.server.protocol import Protocol
from scrutiny.server.protocol.commands import *
from scrutiny.core.variable import *


class TestDataStoreUpdater(unittest.TestCase):

    def make_dummy_entries(self, adress, n, vartype=VariableType.float32):
        dummy_var = Variable('dummy', vartype=vartype, path_segments=['a','b','c'], location=adress, endianness=Endianness.Little)
        for i in range(n):
            entry = DatastoreEntry(DatastoreEntry.EntryType.Var, 'path_%d' % i, variable_def=dummy_var)
            yield entry

    def test_read_request_basic_behavior(self):
        nfloat = 100
        address = 0x1000
        ds = Datastore()
        entries = list(self.make_dummy_entries(address=address, n=nfloat, vartype=VariableType.float32))
        for entry in entries:
            ds.add_entry(entry)
        dispatcher = RequestDispatcher()

        updater = DatastoreUpdater(Protocol(1,0), dispatcher = dispatcher, datastore=ds, read_priority=0, write_priority=0)
        updater.set_max_request_size(1024)  # big enough for all of them
        updater.set_max_response_size(1024) # big enough for all of them
        updater.start()

        for i in range(5):
            updater.process()
            dispatcher.process()

            req_record = dispatcher.pop_next()
            self.assertIsNotNone(req_record)
            self.assertIsNone(dispatcher.pop_next())
            req = req_record.request

            # Make sure that nothing happens until this request is completed.
            updater.process()
            dispatcher.process()
            self.assertIsNone(dispatcher.pop_next(), 'i=%d' % i)

            self.assertEqual(req.cmd, MemoryControl, 'i=%d' % i)
            self.assertEqual(req.subfn, MemoryControl.Subfunction.ReadMemory, 'i=%d' % i)

            request_data = protocol.parse_request(req)
            self.assertEqual(len(request_data['blocks_to_write']), 1, 'i=%d'%i)
            self.assertEqual(request_data['blocks_to_write']['address'], address, 'i=%d'%i)
            self.assertEqual(request_data['blocks_to_write']['length'], nfloat * 4, 'i=%d'%i)

            # Simulate that the response has been received
            block_data = b'\x00'*(nfloat*4)
            block_data[0:3*4] = struct.pack('fff', 1.123, 9.999, -10.26);
            response = protocol.respond_read_memory_blocks([(0x1000, block_data)]);
            req_record.complete(success=True, response = response, response_data=protocol.parse_response(response))

            self.assertEqual(entries[0].get_value(), 1.123, 'i=%d'%i)
            self.assertEqual(entries[1].get_value(), 9.999, 'i=%d'%i)
            self.assertEqual(entries[2].get_value(), -10.26, 'i=%d'%i)
            for entry in entries[3:]:
                self.assertEqual(entry.get_value(), 0)

            # Round trip complete.  Do another round