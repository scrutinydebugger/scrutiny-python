
#    test_tcp_datagrams.py
#        Test the parsing layer used on top of socket to exchange datagrams between clients and server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny.tools.stream_datagrams import StreamMaker, StreamParser
from test import logger
from test import ScrutinyUnitTest
from hashlib import md5
import time

DEFAULT_MTU = 1024*1024

class TestStreamDatagrams(ScrutinyUnitTest):
    def test_stream_maker(self):
        data = bytes( [1,2,3,4] )
        payload = bytes(StreamMaker(mtu=DEFAULT_MTU, use_hash=True).encode(data))
        self.assertEqual(b"<SCRUTINY size=4>\x01\x02\x03\x04" + md5(data).digest(), payload)

        data = bytes( [1,2,3,4] )
        payload = bytes(StreamMaker(mtu=DEFAULT_MTU, use_hash=False).encode(data))
        self.assertEqual(b"<SCRUTINY size=4>\x01\x02\x03\x04", payload)

        with self.assertRaises(Exception):
            StreamMaker(mtu=4, use_hash=False).encode("abcde".encode('ascii'))
        StreamMaker(mtu=4, use_hash=False).encode("abcd".encode('ascii'))   # no exception

    def test_stream_parser_simple_read_hash(self):
        data = bytes( [1,2,3,4] )
        payload = b"<SCRUTINY size=4>" + data + md5(data).digest()

        parser = StreamParser(mtu=DEFAULT_MTU, use_hash=True)
        parser.parse(payload)
        self.assertFalse(parser.queue().empty())
        self.assertEqual(parser.queue().get(), data)      

    def test_stream_parser_simple_read_nohash(self):
        data = bytes( [1,2,3,4] )
        payload = b"<SCRUTINY size=4>" + data

        parser = StreamParser(mtu=DEFAULT_MTU, use_hash=False)
        parser.parse(payload)
        self.assertFalse(parser.queue().empty())
        self.assertEqual(parser.queue().get(), data)        
    
    def test_stream_parser_bad_size(self):
        data = bytes( [1,2,3,4] )
        for i in range (10):
            if i != len(data):
                payload = b"<SCRUTINY size=" + str(i).encode('utf8') + b">" + data + md5(data).digest()
                parser = StreamParser(mtu=DEFAULT_MTU, use_hash=True)
                parser.parse(payload)
                self.assertTrue(parser.queue().empty())
        
    def test_stream_parser_multi_datagrams_single_chunk(self):
        for use_hash in True, False:
            datas = [
                bytes([0x01,0x02,0x03,0x04]),
                bytes([0x11,0x12,0x13,0x14, 0x15, 0x16]),
                bytes([0x21,0x22,0x23]),
            ]

            payload = bytearray()
            payload.extend("garbage!".encode('ascii'))
            for data in datas:
                payload.extend(StreamMaker(mtu=DEFAULT_MTU, use_hash=use_hash).encode(data))
                payload.extend("garbage!...".encode('ascii'))
            
            parser = StreamParser(mtu=DEFAULT_MTU, use_hash=use_hash)
            parser.parse(payload)
            q = parser.queue()
            for i in range(len(datas)):
                self.assertFalse(q.empty(), f"i={i}")
                self.assertEqual(q.get(), datas[i], f"i={i}")
            self.assertTrue(q.empty())



    def test_stream_parser_multi_datagrams_byte_per_bytes(self):
        for use_hash in True, False:
            datas = [
                bytes([0x01,0x02,0x03,0x04]),
                bytes([0x11,0x12,0x13,0x14, 0x15, 0x16]),
                bytes([0x21,0x22,0x23]),
            ]

            payload = bytearray()
            payload.extend("garbage!".encode('ascii'))
            for data in datas:
                payload.extend(StreamMaker(mtu=DEFAULT_MTU, use_hash=use_hash).encode(data))
                payload.extend("garbage!...".encode('ascii'))
            
            parser = StreamParser(mtu=DEFAULT_MTU, use_hash=use_hash)
            for b in payload:
                parser.parse(bytes([b]))
            q = parser.queue()
            for i in range(len(datas)):
                self.assertFalse(q.empty(), f"i={i}")
                self.assertEqual(q.get(), datas[i], f"i={i}")
            self.assertTrue(q.empty())

    def test_stream_parser_timeout(self):
        for use_hash in False, :
            datas = [
                bytes([0x01,0x02,0x03,0x04]),
                bytes([0x11,0x12,0x13,0x14, 0x15, 0x16]),
                bytes([0x21,0x22,0x23]),
            ]

            maker = StreamMaker(mtu=DEFAULT_MTU, use_hash=use_hash)
            payload = bytearray()
            payload.extend("garbage!".encode('ascii'))
            split = None
            for data in datas:
                payload.extend(maker.encode(data))
                if split is None:   # Split the first block, making it invalid after a timeout
                    split = len(payload)-2
                payload.extend("garbage!...".encode('ascii'))
            
            parser = StreamParser(mtu=DEFAULT_MTU, interchunk_timeout=0.2, use_hash=use_hash)
            parser.parse(payload[0:split])
            time.sleep(0.3)
            parser.parse(payload[split:])
            
            q = parser.queue()
            for i in range(1,len(datas)): # Skip the first one
                self.assertFalse(q.empty(), f"i={i}")
                self.assertEqual(q.get(), datas[i], f"i={i}")
            self.assertTrue(q.empty())   

        # reparse everything. Make sure the timeout didn'T break anything
        parser.parse(payload)     
        for i in range(len(datas)):
            self.assertFalse(q.empty(), f"i={i}")
            self.assertEqual(q.get(), datas[i], f"i={i}")
        self.assertTrue(q.empty())

    
    def test_stream_parser_mtu_overflow(self):
        for use_hash in False, :
            datas = [
                bytes([0x01,0x02,0x03,0x04]),
                bytes([0x11,0x12,0x13,0x14, 0x15, 0x16]),   # Will be dropped
                bytes([0x21,0x22,0x23]),
            ]

            maker = StreamMaker(mtu=6, use_hash=use_hash)   # Stream Maker makes bigger payload than the aprser
            payload = bytearray()
            payload.extend("garbage!".encode('ascii'))
            for data in datas:
                payload.extend(maker.encode(data))
                payload.extend("garbage!...".encode('ascii'))
            
            parser = StreamParser(mtu=4, interchunk_timeout=0.2, use_hash=use_hash)
            parser.parse(payload)
            
            q = parser.queue()
            for i in (0,2): # Skip the middle one
                self.assertFalse(q.empty(), f"i={i}")
                self.assertEqual(q.get(), datas[i], f"i={i}")
            self.assertTrue(q.empty())   


if __name__ == '__main__':
    import unittest
    unittest.main()
