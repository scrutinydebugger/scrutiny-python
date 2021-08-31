import unittest
import queue
import logging
import time

from scrutiny.server.protocol import Request, Response, Protocol
import scrutiny.server.protocol.commands as cmd
from scrutiny.server.device.fake_device import FakeDevice

logging.basicConfig(level=logging.DEBUG)

class TestFakeDevice(unittest.TestCase):
    def setUp(self):
        self.s2dq = queue.Queue()
        self.d2sq = queue.Queue()
        self.device = FakeDevice(self.s2dq, self.d2sq)
        self.device.start()
        self.protocol = Protocol(1,0)

    def tearDown(self):
        self.device.stop()

    def send_req(self, req, timeout=0.2):
        self.s2dq.put(req.to_bytes())
        return Response.from_bytes(self.d2sq.get(timeout=timeout))


class TestGetInfo(TestFakeDevice):
    
    def test_get_info_protocol_version(self):
        req = self.protocol.get_protocol_version()
        response = self.send_req(req)
        self.assertEqual(response.command, cmd.GetInfo)
        self.assertEqual(response.subfn, cmd.GetInfo.Subfunction.GetProtocolVersion.value)
        self.assertEqual(response.code, Response.ResponseCode.OK)
        self.assertEqual(response.payload, bytes([1,0]))

    def test_get_info_software_id(self):
        req = self.protocol.get_software_id()
        response = self.send_req(req)

        self.assertEqual(response.command, cmd.GetInfo)
        self.assertEqual(response.subfn, cmd.GetInfo.Subfunction.GetSoftwareId.value)
        self.assertEqual(response.code, Response.ResponseCode.OK)
        self.assertEqual(response.payload, self.device.get_software_id().encode('ascii'))

    def test_get_info_supported_features(self):
        req = self.protocol.get_supported_features()
        response = self.send_req(req)

        self.assertEqual(response.command, cmd.GetInfo)
        self.assertEqual(response.subfn, cmd.GetInfo.Subfunction.GetSupportedFeatures.value)
        self.assertEqual(response.code, Response.ResponseCode.OK)
        self.assertEqual(response.payload, bytes([0xF0]))

class TestMemoryControl(TestFakeDevice):
    def test_read_memory(self):
        req = self.protocol.read_memory_block(1000, 256)
        response = self.send_req(req)

        self.assertEqual(response.command, cmd.MemoryControl)
        self.assertEqual(response.subfn, cmd.MemoryControl.Subfunction.Read.value)
        self.assertEqual(response.code, Response.ResponseCode.OK)
        self.assertEqual(response.payload, bytes(range(256)))


