#    test_comm_handler.py
#        Test the CommHandler that manage the communication with the device a lower level.
#        Converts bytes to Request/Response and flag timeouts
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2023 Scrutiny Debugger

import time

from scrutiny.server.protocol.comm_handler import CommHandler
from scrutiny.server.protocol import Request, Response
from scrutiny.server.protocol.commands import DummyCommand
from scrutiny.server.device.links.dummy_link import DummyLink
from test import ScrutinyUnitTest


class TestCommHandler(ScrutinyUnitTest):
    def setUp(self):
        params = {
            'response_timeout': 0.2
        }

        self.comm_handler = CommHandler(params)
        self.comm_handler.set_link('dummy', {})
        self.comm_handler.open()
        self.link = self.comm_handler.get_link()

    def tearDown(self):
        self.comm_handler.close()

    def compare_responses(self, response1, response2):
        self.assertEqual(response1.command, response2.command)
        self.assertEqual(response1.subfn, response2.subfn)
        self.assertEqual(response1.code, response2.code)
        self.assertEqual(response1.payload, response2.payload)

    def test_simple_exchange(self):
        req = Request(DummyCommand, DummyCommand.Subfunction.SubFn1, payload=bytes([1, 2, 3]))
        self.assertFalse(self.comm_handler.waiting_response())
        self.comm_handler.send_request(req)
        self.assertTrue(self.comm_handler.waiting_response())
        self.comm_handler.process()
        self.assertTrue(self.comm_handler.waiting_response())
        data = self.link.emulate_device_read()
        self.assertEqual(data, req.to_bytes())

        self.assertFalse(self.comm_handler.response_available())
        response = Response(DummyCommand, DummyCommand.Subfunction.SubFn1, Response.ResponseCode.OK, payload=bytes([4, 5, 6]))
        self.link.emulate_device_write(response.to_bytes())
        self.comm_handler.process()
        self.assertTrue(self.comm_handler.waiting_response())
        self.assertTrue(self.comm_handler.response_available())
        response2 = self.comm_handler.get_response()
        self.assertFalse(self.comm_handler.waiting_response())

        self.compare_responses(response, response2)

    def test_multiple_exchange(self):
        req1 = Request(DummyCommand, DummyCommand.Subfunction.SubFn1, payload=bytes([0x1, 0x2, 0x3]))
        req2 = Request(DummyCommand, DummyCommand.Subfunction.SubFn2, payload=bytes([0x4, 0x5, 0x6, 0x7]))
        response1 = Response(DummyCommand, DummyCommand.Subfunction.SubFn1, Response.ResponseCode.OK, payload=bytes([0x11, 0x22, 0x33]))
        response2 = Response(DummyCommand, DummyCommand.Subfunction.SubFn2, Response.ResponseCode.OK, payload=bytes([0x44, 0x55, 0x66, 0x77]))

        self.comm_handler.send_request(req1)
        data = self.link.emulate_device_read()
        self.link.emulate_device_write(response1.to_bytes())
        self.comm_handler.process()
        self.assertTrue(self.comm_handler.response_available())
        response1_ = self.comm_handler.get_response()
        self.assertFalse(self.comm_handler.response_available())
        self.compare_responses(response1_, response1)

        self.comm_handler.send_request(req2)
        data = self.link.emulate_device_read()
        self.link.emulate_device_write(response2.to_bytes())
        self.comm_handler.process()
        self.assertTrue(self.comm_handler.response_available())
        response2_ = self.comm_handler.get_response()
        self.assertFalse(self.comm_handler.response_available())
        self.compare_responses(response2_, response2)

    def test_receive_response_byte_per_byte(self):
        req1 = Request(DummyCommand, DummyCommand.Subfunction.SubFn1, payload=bytes([0x1, 0x2, 0x3]))
        req2 = Request(DummyCommand, DummyCommand.Subfunction.SubFn2, payload=bytes([0x4, 0x5, 0x6, 0x7]))
        response1 = Response(DummyCommand, DummyCommand.Subfunction.SubFn1, Response.ResponseCode.OK, payload=bytes([0x11, 0x22, 0x33]))
        response2 = Response(DummyCommand, DummyCommand.Subfunction.SubFn2, Response.ResponseCode.OK, payload=bytes([0x44, 0x55, 0x66, 0x77]))

        self.comm_handler.send_request(req1)
        data = self.link.emulate_device_read()
        for b in response1.to_bytes():
            self.assertFalse(self.comm_handler.response_available())
            self.link.emulate_device_write(bytes([b]))
            self.comm_handler.process()
        self.assertTrue(self.comm_handler.response_available())
        response1_ = self.comm_handler.get_response()
        self.compare_responses(response1_, response1)

        self.comm_handler.send_request(req2)
        data = self.link.emulate_device_read()
        for b in response2.to_bytes():
            self.assertFalse(self.comm_handler.response_available())
            self.link.emulate_device_write(bytes([b]))
            self.comm_handler.process()
        self.assertTrue(self.comm_handler.response_available())
        response2_ = self.comm_handler.get_response()
        self.compare_responses(response2_, response2)

    def test_receive_response_varying_chunk_size(self):
        req1 = Request(DummyCommand, DummyCommand.Subfunction.SubFn1, payload=bytes([0x1, 0x2, 0x3]))
        response1 = Response(DummyCommand, DummyCommand.Subfunction.SubFn1, Response.ResponseCode.OK, payload=bytes([0x11, 0x22, 0x33]))

        response_data = response1.to_bytes()
        for first_chunk_size in range(len(response_data)):
            self.assertFalse(self.comm_handler.response_available())
            self.comm_handler.send_request(req1)
            data = self.link.emulate_device_read()
            self.assertFalse(self.comm_handler.response_available())
            self.link.emulate_device_write(response_data[0:first_chunk_size])
            self.comm_handler.process()
            self.assertFalse(self.comm_handler.response_available())
            self.link.emulate_device_write(response_data[first_chunk_size:])
            self.comm_handler.process()
            self.assertTrue(self.comm_handler.response_available())
            response1_ = self.comm_handler.get_response()
            self.compare_responses(response1_, response1)

    def test_wait_for_get_no_timeout(self):
        self.comm_handler.params.update({'response_timeout': 0.1})

        req1 = Request(DummyCommand, DummyCommand.Subfunction.SubFn1, payload=bytes([0x1, 0x2, 0x3]))
        response1 = Response(DummyCommand, DummyCommand.Subfunction.SubFn1, Response.ResponseCode.OK, payload=bytes([0x11, 0x22, 0x33]))

        self.comm_handler.send_request(req1)
        data = self.link.emulate_device_read()
        self.link.emulate_device_write(response1.to_bytes())
        self.comm_handler.process()
        time.sleep(0.2)
        self.comm_handler.process()
        self.assertFalse(self.comm_handler.has_timed_out())
        self.assertTrue(self.comm_handler.response_available())
        response1_ = self.comm_handler.get_response()
        self.compare_responses(response1_, response1)

    def test_timeout(self):
        self.comm_handler.params.update({'response_timeout': 0.1})

        req1 = Request(DummyCommand, DummyCommand.Subfunction.SubFn1, payload=bytes([0x1, 0x2, 0x3]))
        response1 = Response(DummyCommand, DummyCommand.Subfunction.SubFn1, Response.ResponseCode.OK, payload=bytes([0x11, 0x22, 0x33]))
        response_data = response1.to_bytes()

        self.comm_handler.send_request(req1)
        data = self.link.emulate_device_read()
        self.link.emulate_device_write(response_data[0:5])
        self.comm_handler.process()
        time.sleep(0.2)
        self.comm_handler.process()
        self.assertTrue(self.comm_handler.has_timed_out())
        self.comm_handler.clear_timeout()
        self.assertFalse(self.comm_handler.has_timed_out())
        self.link.emulate_device_write(response_data[5:])
        self.comm_handler.process()
        self.assertFalse(self.comm_handler.waiting_response())
        self.assertFalse(self.comm_handler.response_available())

        self.comm_handler.send_request(req1)
        self.assertTrue(self.comm_handler.waiting_response())
        self.link.emulate_device_read()
        self.link.emulate_device_write(response_data)
        self.comm_handler.process()
        self.assertTrue(self.comm_handler.response_available())
        response1_ = self.comm_handler.get_response()
        self.compare_responses(response1_, response1)


if __name__ == '__main__':
    import unittest
    unittest.main()
