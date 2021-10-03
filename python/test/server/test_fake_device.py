import unittest
import queue
import logging
import time
import os

from scrutiny.server.protocol import Request, Response, Protocol
import scrutiny.server.protocol.commands as cmd
from scrutiny.server.device.fake_device import FakeDevice
from scrutiny.server.device import FakeDeviceMemdumpDataSource

#logging.basicConfig(level=logging.DEBUG)

class TestFakeDevice(unittest.TestCase):
    def setUp(self):
        self.s2dq = queue.Queue()
        self.d2sq = queue.Queue()
        path_to_memdump = os.path.join(os.path.dirname(__file__), 'unittest_fakedevice_memory.memdump');
        data_source = FakeDeviceMemdumpDataSource(path_to_memdump)
        self.device = FakeDevice(self.s2dq, self.d2sq, data_source)
        self.device.start()
        self.protocol = Protocol(1,0)
        self.device.establish_comm()

    def tearDown(self):
        self.device.stop()

    def send_req(self, req, timeout=0.2):
        no_response = False
        if isinstance(req, Request):
            data = req.to_bytes()
        else:
            data = req
        self.s2dq.put(data)
        try:
            response = Response.from_bytes(self.d2sq.get(timeout=timeout))
            return response
        except queue.Empty:
            no_response = True

        if no_response:
            raise Exception('Did not received a response from the device')  


    def validate_positive_response(self, request, response):
        self.assertEqual(response.command, request.command)
        self.assertEqual(response.subfn, request.subfn)
        self.assertEqual(response.code, Response.ResponseCode.OK)
        return self.protocol.parse_response(response)


class TestEdgeCases(TestFakeDevice):
    def test_invalid_request(self):
        req  = Request(cmd.GetInfo, 0xFB)
        self.send_req(req)


class TestGetInfo(TestFakeDevice):
    
    def test_get_info_protocol_version(self):
        req = self.protocol.get_protocol_version()
        response = self.send_req(req)
        data = self.validate_positive_response(req, response )
        self.assertEqual(data['major'], 1)
        self.assertEqual(data['minor'], 0)

    def test_get_info_software_id(self):
        req = self.protocol.get_software_id()
        response = self.send_req(req)
        data = self.validate_positive_response(req, response )

        self.assertEqual(data['software_id'], self.device.get_software_id())

    def test_get_info_supported_features(self):
        req = self.protocol.get_supported_features()
        response = self.send_req(req)
        data = self.validate_positive_response(req, response )

        self.assertEqual(data['memory_read'], True)
        self.assertEqual(data['memory_write'], True)
        self.assertEqual(data['datalog_acquire'], True)
        self.assertEqual(data['user_command'], True)

class TestMemoryControl(TestFakeDevice):
    def test_read_memory(self):
        req = self.protocol.read_memory_block(0x1000, 256)
        response = self.send_req(req)

        data = self.validate_positive_response(req, response )
        self.assertEqual(data['address'], 0x1000)
        self.assertEqual(data['data'], bytes(range(256)))

    def test_read_memory_out_of_range(self):
        req = self.protocol.read_memory_block(0x1000, 257)
        response = self.send_req(req)
        self.assertEqual(response.code, Response.ResponseCode.FailureToProceed)

        req = self.protocol.read_memory_block(0x2000, 1)
        response = self.send_req(req)
        self.assertEqual(response.code, Response.ResponseCode.FailureToProceed)

    def test_write_memory(self):
        req = self.protocol.write_memory_block(0x2000, bytes(range(256)))
        response = self.send_req(req)
        data = self.validate_positive_response(req, response)
        self.assertEqual(data['address'], 0x2000)
        self.assertEqual(data['length'], 256)

        req = self.protocol.read_memory_block(0x2000, 256)
        response = self.send_req(req)
        data = self.validate_positive_response(req, response)
        self.assertEqual(data['address'], 0x2000)
        self.assertEqual(data['data'], bytes(range(256)))

class TestCommControl(TestFakeDevice):
    def test_heartbeat(self):
        req = self.protocol.comm_heartbeat(0x1234)
        response = self.send_req(req)
        data = self.validate_positive_response(req, response)
        self.assertEqual(data['challenge_response'], 0xEDCB)


