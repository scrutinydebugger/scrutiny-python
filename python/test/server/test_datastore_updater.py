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
from scrutiny.server.protocol import Protocol, Request, Response
from scrutiny.server.protocol.commands import *
from scrutiny.core.variable import *
import random
from dataclasses import dataclass

from typing import List, Dict
from scrutiny.core.typehints import GenericCallback


@dataclass
class BlockToRead:
    address:int
    nfloat:int
    entries:List[DatastoreEntry]

class TestDataStoreUpdater(unittest.TestCase):

    def make_dummy_entries(self, address, n, vartype=VariableType.float32):
        for i in range(n):
            dummy_var = Variable('dummy', vartype=vartype, path_segments=['a','b','c'], location=address+i*vartype.get_size_bit()//8, endianness=Endianness.Little)
            entry = DatastoreEntry(DatastoreEntry.EntryType.Var, 'path_%d' % i, variable_def=dummy_var)
            yield entry

    def test_clusters_list(self):
        ds = Datastore()
        entries1 = list(self.make_dummy_entries(address=0x1000, n=10, vartype=VariableType.float32))
        entries2 = list(self.make_dummy_entries(address=0x1100, n=10, vartype=VariableType.float32))
        entries3 = list(self.make_dummy_entries(address=0x1200, n=10, vartype=VariableType.float32))
        ds.add_entries(entries1 + entries2 + entries3)

        updater = DatastoreUpdater(Protocol(1,0), dispatcher = RequestDispatcher(), datastore=ds, read_priority=0, write_priority=0)
        updater.start()

        for entry in entries1:
            ds.start_watching(entry, 'watcher1', GenericCallback(lambda:None))
            ds.start_watching(entry, 'watcher2', GenericCallback(lambda:None))

        for entry in entries2[4:]:
            ds.start_watching(entry, 'watcher1', GenericCallback(lambda:None))

        for entry in entries3:
            ds.start_watching(entry, 'watcher1', GenericCallback(lambda:None))

        for entry in entries1:
            ds.stop_watching(entry, 'watcher2')

        ds.stop_watching(entries1[0], 'watcher1')
        
        for entry in entries3[1:9]:
            ds.stop_watching(entry, 'watcher1')


        clusters=updater.get_cluster_list()

        self.assertEqual(len(clusters), 4)
        self.assertEqual(clusters[0].start_addr, 0x1000+1*4)
        self.assertEqual(clusters[0].size, 9*4)

        self.assertEqual(clusters[1].start_addr, 0x1100+4*4)
        self.assertEqual(clusters[1].size, 6*4)

        self.assertEqual(clusters[2].start_addr, 0x1200)
        self.assertEqual(clusters[2].size, 1*4)

        self.assertEqual(clusters[3].start_addr, 0x1200 + 4*9)
        self.assertEqual(clusters[3].size, 1*4)

    def generic_test_read_block_sequence(self, expected_blocks_sequence, updater, dispatcher, niter=5):
        #Run the sequence 5 times, just to be sure nothing goes wrong 
        for i in range(niter):
            for expected_block_list in expected_blocks_sequence:
                updater.process()
                dispatcher.process()

                req_record = dispatcher.pop_next()
                self.assertIsNotNone(req_record)
                self.assertIsNone(dispatcher.pop_next())
                req = req_record.request # That out request

                # Make sure that nothing happens until this request is completed.
                updater.process()
                dispatcher.process()
                self.assertIsNone(dispatcher.pop_next(), 'iter=%d' % i)

                # First request should be a read of the 2 first blocks
                self.assertEqual(req.cmd, MemoryControl, 'iter=%d' % i)
                self.assertEqual(req.subfn, MemoryControl.Subfunction.ReadMemory, 'iter=%d' % i)

                # Make sure the request contains the 2 expected blocks
                request_data = protocol.parse_request(req)
                self.assertEqual(len(request_data['blocks_to_read']), len(expected_block_list), 'iter=%d'%i)
                j=0
                for expected_block in expected_block_list: 
                    self.assertEqual(request_data['blocks_to_read'][j]['address'], expected_block.address, 'iter=%d'%i)
                    self.assertEqual(request_data['blocks_to_read'][j]['length'], expected_block.nfloat * 4, 'iter=%d'%i)
                    j+=1
               
                # Simulate that the response has been received
                block_list = []
                data_lut:Dict[BlockToRead, List[float]] = {} # To remember to random value we'll generate
                for expected_block in expected_block_list:
                    values = [random.random() for x in range(expected_block.nfloat)]
                    data_lut[expected_block] = values   # Remember for assertion later
                    block_data = struct.pack('<f'*expected_block.nfloat, *values)    # Make memory dump
                    block_list.append( (expected_block.address, block_data) )
                
                response = protocol.respond_read_memory_blocks(block_list);
                req_record.complete(success=True, response = response, response_data=protocol.parse_response(response))
                # By completing the request. Success callback should be called making the datastore updater update the datastore

                for expected_block in expected_block_list:
                    values = data_lut[expected_block]  # Get back our value list
                    for j in range(len(expected_block.entries)):
                        # Let's validate that the datastore is updated
                        self.assertEqual(expected_block.entries[j].get_value(), values[j], 'iter=%d'%i)


    # Here we have a set of datastore entries that are contiguous in memory.
    # We read them all in a single block (no limitation) and make sure the values are good.
    # We expect the datastore updater to keep asking for updates, so we run the sequence 5 times
    @unittest.skip("Not implemented yet")
    def test_read_request_basic_behavior(self):
        nfloat = 100
        address = 0x1000
        ds = Datastore()
        entries = list(self.make_dummy_entries(address=address, n=nfloat, vartype=VariableType.float32))
        for entry in entries:
            ds.add_entry(entry)
        dispatcher = RequestDispatcher()
        
        protocol = Protocol(1,0)
        protocol.set_address_size_bits(32)
        updater = DatastoreUpdater(protocol, dispatcher = dispatcher, datastore=ds, read_priority=0, write_priority=0)
        updater.set_max_request_size(1024)  # big enough for all of them
        updater.set_max_response_size(1024) # big enough for all of them
        updater.start()

        expected_blocks_sequence = [
            [BlockToRead(address, nfloat, entries)]
            ]

        self.generic_test_read_block_sequence(expected_blocks_sequence, updater, dispatcher, niter=5)


    # Here, we define 3 non-contiguous block of memory and impose a limit on the request size to allow only 2 blocks read per request.
    # We make sure that blocks are completely read.
    @unittest.skip("Not implemented yet")
    def test_read_request_multiple_blocks_2blocks_per_req(self):
        nfloat1 = 10
        nfloat2 = 20
        nfloat3 = 30
        address1 = 0x1000
        address2 = 0x2000
        address3 = 0x3000
        ds = Datastore()
        entries1 = list(self.make_dummy_entries(address=address1, n=nfloat1, vartype=VariableType.float32))
        entries2 = list(self.make_dummy_entries(address=address2, n=nfloat2, vartype=VariableType.float32))
        entries3 = list(self.make_dummy_entries(address=address3, n=nfloat3, vartype=VariableType.float32))
        for entry in entries1+entries2+entries3:
            ds.add_entry(entry)
        dispatcher = RequestDispatcher()
        protocol = Protocol(1,0)
        updater = DatastoreUpdater(protocol, dispatcher = dispatcher, datastore=ds, read_priority=0, write_priority=0)
        updater.set_max_request_size(Request.OVERHEAD_SIZE + protocol.read_memory_request_size_per_block()*2)  # 2 block per request
        updater.set_max_response_size(1024)  # Non-limiting here
        updater.start()

        # The expected sequence of block will be : 1,2 - 3,1 - 2,3 - 1,2 - etc
        expected_blocks_sequence = [
            [BlockToRead(address1, nfloat1, entries1), BlockToRead(address2, nfloat2, entries2)],
            [BlockToRead(address3, nfloat3, entries3), BlockToRead(address1, nfloat1, entries1)],
            [BlockToRead(address2, nfloat2, entries2), BlockToRead(address3, nfloat3, entries3)]                        
            ]

        self.generic_test_read_block_sequence(expected_blocks_sequence, updater, dispatcher, niter=5)


    @unittest.skip("Not implemented yet")
    def test_read_request_multiple_blocks_10_items_per_response(self):
        nfloat = 15
        address = 0x1000
        ds = Datastore()
        entries = list(self.make_dummy_entries(address=address, n=nfloat, vartype=VariableType.float32))
        
        for entry in entries:
            ds.add_entry(entry)
        
        dispatcher = RequestDispatcher()
        protocol = Protocol(1,0)
        updater = DatastoreUpdater(protocol, dispatcher = dispatcher, datastore=ds, read_priority=0, write_priority=0)
        updater.set_max_request_size(1024)  # Non-limiting here
        updater.set_max_response_size(Response.OVERHEAD_SIZE + 10 * (protocol.read_memory_response_overhead_size_per_block() + 4))  
        updater.start()

        # The expected sequence of block will be : 1,2 - 3,1 - 2,3 - 1,2 - etc
        expected_blocks_sequence = [
            [BlockToRead(address, 10, entries[0:10])],
            [BlockToRead(address + 10*4, 5, entries[10:15]), BlockToRead(address, 5, entries[0:5])],
            [BlockToRead(address + 5*4, 10, entries[5:15])]                        
            ]

        self.generic_test_read_block_sequence(expected_blocks_sequence, updater, dispatcher, niter=5)
