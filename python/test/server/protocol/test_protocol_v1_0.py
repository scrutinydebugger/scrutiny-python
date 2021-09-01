import unittest
from scrutiny.server.protocol import Protocol
from scrutiny.server.protocol.datalog_conf import DatalogConfiguration
from scrutiny.core import VariableType
import struct

from scrutiny.server.protocol.crc32 import crc32

class TestProtocolV1_0(unittest.TestCase):

    def setUp(self):
        self.proto = Protocol(1, 0)

    def append_crc(self, data):
        return data + struct.pack('>L', crc32(data))

    def assert_req_bytes(self, req, data):
        self.assertEqual(req.to_bytes(), self.append_crc(bytes(data)))

#===================================
    def test_get_protocol_version(self):
        req = self.proto.get_protocol_version()
        self.assert_req_bytes(req, [1,1,0,0])
        data = self.proto.parse_request(req)

    def test_get_software_id(self):
        req = self.proto.get_software_id()
        self.assert_req_bytes(req, [1,2,0,0])
        data = self.proto.parse_request(req)

    def test_get_supported_features(self):
        req = self.proto.get_supported_features()
        self.assert_req_bytes(req, [1,3,0,0])
        data = self.proto.parse_request(req)

    def test_read_memory_block(self):
        req = self.proto.read_memory_block(0x12345678, 0x123)
        self.assert_req_bytes(req, [3,1,0,6, 0x12, 0x34, 0x56, 0x78, 0x1, 0x23])
        data = self.proto.parse_request(req)
        self.assertEqual(data['address'], 0x12345678)
        self.assertEqual(data['length'], 0x123)

    def test_write_memory_block(self):
        req = self.proto.write_memory_block(0x12345678, bytes([0x11, 0x22, 0x33]))
        self.assert_req_bytes(req, [3,2,0,7, 0x12, 0x34, 0x56, 0x78, 0x11, 0x22, 0x33])
        data = self.proto.parse_request(req)
        self.assertEqual(data['address'], 0x12345678)
        self.assertEqual(data['data'], bytes([0x11, 0x22, 0x33]))

    def test_heartbeat_ping(self):
        req = self.proto.ping()
        self.assert_req_bytes(req, [4,1,0,0])
        data = self.proto.parse_request(req)

    def test_heartbeat_pong(self):
        req = self.proto.pong()
        self.assert_req_bytes(req, [4,2,0,0])
        data = self.proto.parse_request(req)

    def test_datalog_get_targets(self):
        req = self.proto.datalog_get_targets()
        self.assert_req_bytes(req, [6,1,0,0])
        data = self.proto.parse_request(req)

    def test_datalog_get_buffer_size(self):
        req = self.proto.datalog_get_bufsize()
        self.assert_req_bytes(req, [6,2,0,0])
        data = self.proto.parse_request(req)

    def test_datalog_get_buffer_size(self):
        req = self.proto.datalog_get_sampling_rates()
        self.assert_req_bytes(req, [6,3,0,0])
        data = self.proto.parse_request(req)

    def test_datalog_configure_log(self):
        conf = DatalogConfiguration()
        conf.add_watch(0x1234, 2)
        conf.add_watch(0x1111, 4)
        conf.add_watch(0x2222, 4)
        conf.destination = 0
        conf.sample_rate = 100000
        conf.decimation = 5
        conf.trigger.condition = DatalogConfiguration.TriggerCondition.EQUAL
        conf.trigger.operand1 = DatalogConfiguration.WatchOperand(address=0x99887766, length=4, interpret_as=VariableType.float32)
        conf.trigger.operand2 = DatalogConfiguration.ConstOperand(666)

        data = struct.pack('>BfBH', 0, 100000, 5, 3)    # destination, sample rate, decimation, num watch
        data += struct.pack('>LHLHLH', 0x1234, 2, 0x1111, 4, 0x2222, 4) # watch def
        data += b'\x00' # condition
        data += struct.pack('>BLBB',  2, 0x99887766, 4, 22)  # operand type, operand data
        data += struct.pack('>Bf',  1, 666)  # operand type, operand data

        payload = bytes([6,4]) + struct.pack('>H', len(data)) + data
        req = self.proto.datalog_configure_log(conf)
        self.assert_req_bytes(req, payload)
        data = self.proto.parse_request(req)

        conf2 = data['configuration']
        self.assertEqual(len(conf2.watches), 3)
        self.assertEqual(conf2.watches[0].address, 0x1234)
        self.assertEqual(conf2.watches[0].length, 2)
        self.assertEqual(conf2.watches[1].address, 0x1111)
        self.assertEqual(conf2.watches[1].length, 4)
        self.assertEqual(conf2.watches[2].address, 0x2222)
        self.assertEqual(conf2.watches[2].length, 4)

        self.assertEqual(conf.destination, conf2.destination)
        self.assertEqual(conf.sample_rate, conf2.sample_rate)
        self.assertEqual(conf.decimation, conf2.decimation)
        self.assertEqual( conf.trigger.condition,  conf2.trigger.condition)
        self.assertIsInstance( conf.trigger.operand1,   DatalogConfiguration.WatchOperand)
        self.assertEqual( conf.trigger.operand1.address,  conf2.trigger.operand1.address)
        self.assertEqual( conf.trigger.operand1.length,  conf2.trigger.operand1.length)
        self.assertEqual( conf.trigger.operand1.interpret_as,  conf2.trigger.operand1.interpret_as)
        self.assertIsInstance( conf.trigger.operand2,   DatalogConfiguration.ConstOperand)
        self.assertEqual( conf.trigger.operand2.value,  conf2.trigger.operand2.value)


    def test_datalog_list_records(self):
        req = self.proto.datalog_get_list_recording()
        self.assert_req_bytes(req, [6,5,0,0])
        data = self.proto.parse_request(req)

    def test_datalog_read_recording(self):
        req = self.proto.datalog_read_recording(record_id = 0x1234)
        self.assert_req_bytes(req, [6,6,0,2, 0x12, 0x34])
        data = self.proto.parse_request(req)
        self.assertEqual(data['record_id'], 0x1234)

    def test_datalog_arm_log(self):
        req = self.proto.datalog_arm()
        self.assert_req_bytes(req, [6,7,0,0])
        data = self.proto.parse_request(req)

    def test_datalog_disarm_log(self):
        req = self.proto.datalog_disarm()
        self.assert_req_bytes(req, [6,8,0,0])
        data = self.proto.parse_request(req)

    def test_datalog_get_log_status(self):
        req = self.proto.datalog_status()
        self.assert_req_bytes(req, [6,9,0,0])
        data = self.proto.parse_request(req)

    