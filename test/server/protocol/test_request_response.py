#    test_request_response.py
#        Test for the protocol Request and Response class.
#        Ensure that byte encoding/decoding works properly
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

from scrutiny.server.protocol import Request, Response
from test import ScrutinyUnitTest


class TestMessage(ScrutinyUnitTest):
    def test_request(self):
        msg = Request(command=1, subfn=0x34, payload=bytes([1, 2, 3, 4]))
        data = msg.to_bytes()
        self.assertEqual(data[:-4], bytes([1, 0x34, 0, 4, 1, 2, 3, 4]))
        msg2 = Request.from_bytes(data)

        self.assertEqual(msg.command, msg2.command)
        self.assertEqual(msg.subfn, msg2.subfn)
        self.assertEqual(msg.payload, msg2.payload)

    def test_request_no_data(self):
        msg = Request(command=1, subfn=0x34)
        data = msg.to_bytes()
        self.assertEqual(data[:-4], bytes([1, 0x34, 0, 0]))
        msg2 = Request.from_bytes(data)

        self.assertEqual(msg.command, msg2.command)
        self.assertEqual(msg.subfn, msg2.subfn)
        self.assertEqual(msg.payload, msg2.payload)

    def test_request_meta(self):
        msg = Request(command=1, subfn=0x34, payload=bytes([1, 2, 3, 4]))
        str(msg)
        msg.__repr__()

    def test_response(self):
        msg = Response(command=1, subfn=0x34, code=1, payload=bytes([1, 2, 3, 4]))
        data = msg.to_bytes()
        self.assertEqual(data[:-4], bytes([0x81, 0x34, 1, 0, 4, 1, 2, 3, 4]))
        msg2 = Response.from_bytes(data)

        self.assertEqual(msg.command, msg2.command)
        self.assertEqual(msg.subfn, msg2.subfn)
        self.assertEqual(msg.payload, msg2.payload)

    def test_response_no_data(self):
        msg = Response(command=1, subfn=0x34, code=1)
        data = msg.to_bytes()
        self.assertEqual(data[:-4], bytes([0x81, 0x34, 1, 0, 0]))
        msg2 = Response.from_bytes(data)

        self.assertEqual(msg.command, msg2.command)
        self.assertEqual(msg.subfn, msg2.subfn)
        self.assertEqual(msg.code, msg2.code)
        self.assertEqual(msg.payload, msg2.payload)

    def test_response_wrong_length(self):
        with self.assertRaises(Exception):
            Response.from_bytes(bytes([0x81, 0, 0, 0, 5, 1, 2, 3, 4]))  # Missing one data bytes

        with self.assertRaises(Exception):
            Response.from_bytes(bytes([0x81, 0, 0, 0, 5, 1, 2, 3, 4, 5, 6]))  # One extra byte

    def test_response_meta(self):
        msg = Response(command=1, subfn=0x34, code=1, payload=bytes([1, 2, 3, 4]))
        str(msg)
        msg.__repr__()

    # Make sure size calculation is consistent
    def test_size(self):
        empty_response = Response(command=1, subfn=0x34, code=1)
        self.assertEqual(Response.OVERHEAD_SIZE, empty_response.size())
        self.assertEqual(Response.OVERHEAD_SIZE, len(empty_response.to_bytes()))

        response_4bytes = Response(command=1, subfn=0x34, code=1, payload=b'\x00' * 4)
        self.assertEqual(Response.OVERHEAD_SIZE + 4, response_4bytes.size())
        self.assertEqual(Response.OVERHEAD_SIZE + 4, len(response_4bytes.to_bytes()))

        empty_request = Request(command=1, subfn=0x34)
        self.assertEqual(Request.OVERHEAD_SIZE, empty_request.size())
        self.assertEqual(Request.OVERHEAD_SIZE, len(empty_request.to_bytes()))

        request_4bytes = Request(command=1, subfn=0x34, payload=b'\x00' * 4)
        self.assertEqual(Request.OVERHEAD_SIZE + 4, request_4bytes.size())
        self.assertEqual(Request.OVERHEAD_SIZE + 4, len(request_4bytes.to_bytes()))


if __name__ == '__main__':
    import unittest
    unittest.main()
