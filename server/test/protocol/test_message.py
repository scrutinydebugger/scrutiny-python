import unittest
from server.protocol import Request, Response

class TestMessage(unittest.TestCase):
    def test_request(self):
        msg = Request(command = 0x12, subfn=0x34, payload=bytes([1,2,3,4]))
        data = msg.to_bytes()
        self.assertEqual(data[:-4], bytes([0x12, 0x34, 0, 4, 1,2,3,4]))
        msg2 = Request.from_bytes(data)

        self.assertEqual(msg.command, msg2.command)
        self.assertEqual(msg.subfn, msg2.subfn)
        self.assertEqual(msg.payload, msg2.payload)

    def test_request_no_data(self):
        msg = Request(command = 0x12, subfn=0x34)
        data = msg.to_bytes()
        self.assertEqual(data[:-4], bytes([0x12, 0x34, 0, 0]))
        msg2 = Request.from_bytes(data)

        self.assertEqual(msg.command, msg2.command)
        self.assertEqual(msg.subfn, msg2.subfn)
        self.assertEqual(msg.payload, msg2.payload)

    def test_response(self):
        msg = Response(command = 0x12, subfn=0x34, code=1, payload=bytes([1,2,3,4]))
        data = msg.to_bytes()
        self.assertEqual(data[:-4], bytes([0x92, 0x34, 1, 0, 4, 1,2,3,4]))
        msg2 = Response.from_bytes(data)

        self.assertEqual(msg.command, msg2.command)
        self.assertEqual(msg.subfn, msg2.subfn)
        self.assertEqual(msg.payload, msg2.payload)

    def test_response_no_data(self):
        msg = Response(command = 0x12, subfn=0x34, code=1)
        data = msg.to_bytes()
        self.assertEqual(data[:-4], bytes([0x92, 0x34, 1, 0, 0]))
        msg2 = Response.from_bytes(data)

        self.assertEqual(msg.command, msg2.command)
        self.assertEqual(msg.subfn, msg2.subfn)
        self.assertEqual(msg.code, msg2.code)
        self.assertEqual(msg.payload, msg2.payload)
