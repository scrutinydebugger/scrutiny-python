
#    test_tcp_datagrams.py
#        Test the parsing layer used on top of socket to exchange datagrams between clients and server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny.tools.tcp_datagrams import StreamMaker, StreamParser
from test import logger
from test import ScrutinyUnitTest
from hashlib import sha1
import time


class TestTCPDatagrams(ScrutinyUnitTest):
    def test_stream_maker(self):
        data = bytes( [1,2,3,4] )
        payload = bytes(StreamMaker.encode(data))
        self.assertEqual(b"<SCRUTINY size=00000004>\x01\x02\x03\x04" + sha1(data).digest(), payload)

    def test_stream_parser_simple_read(self):
        data = bytes( [1,2,3,4] )
        payload = b"<SCRUTINY size=4>" + data + sha1(data).digest()

        parser = StreamParser()
        parser.parse(payload)
        self.assertFalse(parser.queue().empty())
        self.assertEqual(parser.queue().get(), data)
    
    def test_stream_parser_bad_size(self):
        data = bytes( [1,2,3,4] )
        for i in range (10):
            if i != len(data):
                payload = b"<SCRUTINY size=" + str(i).encode('utf8') + b">" + data + sha1(data).digest()
                parser = StreamParser()
                parser.parse(payload)
                self.assertTrue(parser.queue().empty())
        
    def test_stream_parser_multi_datagrams_single_chunk(self):
        datas = [
            bytes([0x01,0x02,0x03,0x04]),
            bytes([0x11,0x12,0x13,0x14, 0x15, 0x16]),
            bytes([0x21,0x22,0x23]),
        ]

        payload = bytearray()
        payload.extend("garbage!".encode('ascii'))
        for data in datas:
            payload.extend(StreamMaker.encode(data))
            payload.extend("garbage!...".encode('ascii'))
        
        parser = StreamParser()
        parser.parse(payload)
        q = parser.queue()
        for i in range(len(datas)):
            self.assertFalse(q.empty(), f"i={i}")
            self.assertEqual(q.get(), datas[i], f"i={i}")
        self.assertTrue(q.empty())


    def test_stream_parser_multi_datagrams_byte_per_bytes(self):
        datas = [
            bytes([0x01,0x02,0x03,0x04]),
            bytes([0x11,0x12,0x13,0x14, 0x15, 0x16]),
            bytes([0x21,0x22,0x23]),
        ]

        payload = bytearray()
        payload.extend("garbage!".encode('ascii'))
        for data in datas:
            payload.extend(StreamMaker.encode(data))
            payload.extend("garbage!...".encode('ascii'))
        
        parser = StreamParser()
        for b in payload:
            parser.parse(bytes([b]))
        q = parser.queue()
        for i in range(len(datas)):
            self.assertFalse(q.empty(), f"i={i}")
            self.assertEqual(q.get(), datas[i], f"i={i}")
        self.assertTrue(q.empty())

    def test_stream_parser_timeout(self):
        datas = [
            bytes([0x01,0x02,0x03,0x04]),
            bytes([0x11,0x12,0x13,0x14, 0x15, 0x16]),
            bytes([0x21,0x22,0x23]),
        ]

        payload = bytearray()
        payload.extend("garbage!".encode('ascii'))
        split = None
        for data in datas:
            payload.extend(StreamMaker.encode(data))
            if split is None:   # Split the first block, making it invalid after a timeout
                split = len(payload)-5
            payload.extend("garbage!...".encode('ascii'))
        
        parser = StreamParser(interchunk_timeout=0.2)
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

if __name__ == '__main__':
    import unittest
    unittest.main()
