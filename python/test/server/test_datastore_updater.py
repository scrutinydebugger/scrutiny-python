#    test_datastore_updater.py
#        Test the Datastore Updater capability to generate requests based on variable subscription
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import unittest
import random
from dataclasses import dataclass
from sortedcontainers import SortedSet

from scrutiny.server.datastore import Datastore, DatastoreEntry
from scrutiny.server.device.request_generator.datastore_updater import DatastoreUpdater, DataStoreEntrySortableByAddress
from scrutiny.server.device.request_dispatcher import RequestDispatcher
from scrutiny.server.protocol import Protocol, Request, Response
from scrutiny.server.protocol.commands import *
from scrutiny.core.variable import *

from typing import List, Dict
from scrutiny.core.typehints import GenericCallback

class BlockToRead:
    address:int
    nfloat:int
    entries:List[DatastoreEntry]

    def __init__(self, address:int, nfloat:int, entries:List[DatastoreEntry]):
        self.address = address
        self.nfloat = nfloat
        self.entries = entries

    def __repr__(self):
        return '<Block: 0x%08x with %d float>' % (self.address, self.nfloat)

def make_dummy_entries(address, n, vartype=VariableType.float32):
    for i in range(n):
        dummy_var = Variable('dummy', vartype=vartype, path_segments=['a','b','c'], location=address+i*vartype.get_size_bit()//8, endianness=Endianness.Little)
        entry = DatastoreEntry(DatastoreEntry.EntryType.Var, 'path_%d' % i, variable_def=dummy_var)
        yield entry

def d2f(d):
    return struct.unpack('f', struct.pack('f', d))[0]

class TestDataStoreUpdaterBasicReadOperation(unittest.TestCase):
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
        is_sorted = all(entries_sorted[i] <= entries_sorted[i+1] for i in range(len(entries_sorted) - 1))
        self.assertTrue(is_sorted)

        for entry in entries:
            theset.discard(DataStoreEntrySortableByAddress(entry))

        self.assertEqual(len(theset), 0)


    def generic_test_read_block_sequence(self, expected_blocks_sequence, updater, dispatcher, protocol, niter=5): 
        for i in range(niter):
            for expected_block_list in expected_blocks_sequence:
                updater.process()
                dispatcher.process()

                req_record = dispatcher.pop_next()
                self.assertIsNotNone(req_record, 'iter=%d' % i)
                self.assertIsNone(dispatcher.pop_next(), 'iter=%d' % i)
                req = req_record.request # That out request

                # Make sure that nothing happens until this request is completed.
                updater.process()
                dispatcher.process()
                self.assertIsNone(dispatcher.pop_next(), 'iter=%d' % i)

                # First request should be a read of the 2 first blocks
                self.assertEqual(req.command, MemoryControl, 'iter=%d' % i)
                self.assertEqual(MemoryControl.Subfunction(req.subfn), MemoryControl.Subfunction.Read, 'iter=%d' % i)

                # Make sure the request contains the 2 expected blocks
                request_data = protocol.parse_request(req)
                self.assertEqual(len(request_data['blocks_to_read']), len(expected_block_list), 'iter=%d'%i)
                j=0
                for expected_block in expected_block_list: 
                    self.assertEqual(request_data['blocks_to_read'][j]['address'], expected_block.address, 'iter=%d, block=%d' % (i,j))
                    self.assertEqual(request_data['blocks_to_read'][j]['length'], expected_block.nfloat * 4, 'iter=%d, block=%d' % (i,j))
                    j+=1
               
                # Simulate that the response has been received
                block_list = []
                data_lut:Dict[BlockToRead, List[float]] = {} # To remember to random value we'll generate
                for expected_block in expected_block_list:
                    values = [d2f(random.random()) for x in range(expected_block.nfloat)]
                    data_lut[expected_block] = values   # Remember for assertion later
                    block_data = struct.pack('<'+'f'*expected_block.nfloat, *values)    # Make memory dump
                    block_list.append( (expected_block.address, block_data) )
                
                response = protocol.respond_read_memory_blocks(block_list);
                req_record.complete(success=True, response = response)
                # By completing the request. Success callback should be called making the datastore updater update the datastore

                for expected_block in expected_block_list:
                    values = data_lut[expected_block]  # Get back our value list
                    for j in range(len(expected_block.entries)):
                        # Let's validate that the datastore is updated
                        self.assertEqual(expected_block.entries[j].get_value(), values[j], 'iter=%d, block=%d' % (i,j))


    # Here we have a set of datastore entries that are contiguous in memory.
    # We read them all in a single block (no limitation) and make sure the values are good.
    # We expect the datastore updater to keep asking for updates, so we run the sequence 5 times
    def test_read_request_basic_behavior(self):
        nfloat = 100
        address = 0x1000
        ds = Datastore()
        entries = list(make_dummy_entries(address=address, n=nfloat, vartype=VariableType.float32))
        ds.add_entries(entries)
        dispatcher = RequestDispatcher()
    
        protocol = Protocol(1,0)
        protocol.set_address_size_bits(32)
        updater = DatastoreUpdater(protocol, dispatcher = dispatcher, datastore=ds, read_priority=0, write_priority=0)
        updater.set_max_request_size(1024)  # big enough for all of them
        updater.set_max_response_size(1024) # big enough for all of them
        updater.start()

        for entry in entries:
            ds.start_watching(entry, 'unittest', GenericCallback(lambda *args, **kwargs:None))

        expected_blocks_sequence = [
            [BlockToRead(address, nfloat, entries)]
            ]

        self.generic_test_read_block_sequence(expected_blocks_sequence, updater, dispatcher, protocol, niter=5)


    # Here, we define 3 non-contiguous block of memory and impose a limit on the request size to allow only 2 blocks read per request.
    # We make sure that blocks are completely read.
    def test_read_request_multiple_blocks_2blocks_per_req(self):
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
        all_entries = entries1+entries2+entries3
        ds.add_entries(all_entries)
        dispatcher = RequestDispatcher()
        protocol = Protocol(1,0)
        updater = DatastoreUpdater(protocol, dispatcher = dispatcher, datastore=ds, read_priority=0, write_priority=0)
        updater.set_max_request_size(Request.OVERHEAD_SIZE + protocol.read_memory_request_size_per_block()*2)  # 2 block per request
        updater.set_max_response_size(1024)  # Non-limiting here
        updater.start()

        for entry in all_entries:
            ds.start_watching(entry, 'unittest', GenericCallback(lambda *args, **kwargs:None))

        # The expected sequence of block will be : 1,2 - 3,1 - 2,3 - 1,2 - etc
        expected_blocks_sequence = [
            [BlockToRead(address1, nfloat1, entries1), BlockToRead(address2, nfloat2, entries2)],
            [BlockToRead(address1, nfloat1, entries1), BlockToRead(address3, nfloat3, entries3)],
            [BlockToRead(address2, nfloat2, entries2), BlockToRead(address3, nfloat3, entries3)]                        
            ]

        self.generic_test_read_block_sequence(expected_blocks_sequence, updater, dispatcher, protocol, niter=5)


    # Here we make read entries, but response has enough space for only 10 blocks of 1 entry.
    # Make sure this happens
    def test_read_request_multiple_blocks_limited_by_response_size(self):
        nfloat = 15
        entries = []
        for i in range(nfloat): 
            entries += list(make_dummy_entries(address=i*0x100, n=1, vartype=VariableType.float32))
        
        ds = Datastore()
        ds.add_entries(entries)
        
        dispatcher = RequestDispatcher()
        protocol = Protocol(1,0)
        updater = DatastoreUpdater(protocol, dispatcher = dispatcher, datastore=ds, read_priority=0, write_priority=0)
        updater.set_max_request_size(1024)  # Non-limiting here
        updater.set_max_response_size(Response.OVERHEAD_SIZE + protocol.read_memory_response_overhead_size_per_block()*10 + 4*10)  
        updater.start()

        for entry in entries:
            ds.start_watching(entry, 'unittest', GenericCallback(lambda *args, **kwargs:None))

        # The expected sequence of block will be : 1,2 - 3,1 - 2,3 - 1,2 - etc
        # Sorted by address.
        expected_blocks_sequence = [
            [BlockToRead(i*0x100, 1, entries[i:i+1]) for i in range(10)],
            [BlockToRead(i*0x100, 1, entries[i:i+1]) for i in range(5)] + [BlockToRead((10+i)*0x100, 1, entries[10+i:10+i+1]) for i in range(5)],
            [BlockToRead((i+5)*0x100 , 1, entries[5+i:5+i+1]) for i in range(10)]                        
            ]

        self.generic_test_read_block_sequence(expected_blocks_sequence, updater, dispatcher, protocol, niter=5)



class TestDataStoreUpdaterComplexReadOperation(unittest.TestCase):
    # Here we make a complex pattern of variables tor ead.
    # Diferent types,  different blocks, forbidden regions, request and response size limit.
    # We make sure that all entries are updated in a round robin scheme. 
    # So everyone is updated. Nobody is updated twice unless everybody else us updated.

    def setUp(self):
        self.callback_count_map = {}

    def value_change_callback1(self, owner, entry):
        if entry not in self.callback_count_map:
            self.callback_count_map[entry] = 0

        self.callback_count_map[entry]+=1

    def get_callback_count_min_max(self):
        low = None
        high = None

        for entry in self.callback_count_map:
            v =  self.callback_count_map[entry]
            if low is None or v<low:
                low = v

            if high is None or v>high:
                high = v

        return (low, high)

    
    def test_read_request_multiple_blocks_complex_pattern(self):
        max_request_size = 128
        max_response_size = 128

        entries = list(make_dummy_entries(address=0x1000, n=1, vartype=VariableType.float32))
        entries += list(make_dummy_entries(address=0x1004, n=2, vartype=VariableType.uint16))
        entries += list(make_dummy_entries(address=0x2000, n=0x100, vartype=VariableType.sint8))
        entries += list(make_dummy_entries(address=0x2100, n=0x100, vartype=VariableType.uint8))
        entries += list(make_dummy_entries(address=0x2200, n=0x100, vartype=VariableType.boolean))
        entries += list(make_dummy_entries(address=0x3000, n=0x100, vartype=VariableType.uint32))
        
        for i in range(0x100):
            entries += list(make_dummy_entries(address=0x10000 + i*0x10, n=1, vartype=VariableType.uint8))

        ds = Datastore()
        ds.add_entries(entries)
        
        dispatcher = RequestDispatcher()
        protocol = Protocol(1,0)
        updater = DatastoreUpdater(protocol=protocol, dispatcher = dispatcher, datastore=ds, read_priority=0, write_priority=0)
        updater.set_max_request_size(128)
        updater.set_max_response_size(128)  
        updater.start()

        for entry in entries:
            ds.start_watching(entry, 'unittest', GenericCallback(self.value_change_callback1))

        # We process the updater until we do 10 round of updates or something fails
        max_loop = 10000
        loop_count = 0
        while loop_count < max_loop:
            updater.process()
            dispatcher.process()

            record = dispatcher.pop_next()
            self.assertIsNotNone(record)
            
            self.assertLessEqual(record.request.size(), max_request_size)
            response_block = []
            request_data = protocol.parse_request(record.request)
            self.assertTrue(request_data['valid'])
            
            for block in request_data['blocks_to_read']:
                response_block.append( (block['address'], b'\x00'*block['length']) ) 

            response = protocol.respond_read_memory_blocks(response_block)
            self.assertLessEqual(response.size(), max_response_size)
            record.complete(success=True, response = response)

            low, high = self.get_callback_count_min_max()
            self.assertIsNotNone(low)
            self.assertIsNotNone(high)
            self.assertGreaterEqual(high, low)    # High should be greater than 1
            self.assertLessEqual(high-low, 1)     # High should be equal to low or low+1. This ensure that round robin is working fine

            if low > 10:
                break

            loop_count+=1

        self.assertLess(loop_count, max_loop) # Make sure we haven't exited because nothing happens
