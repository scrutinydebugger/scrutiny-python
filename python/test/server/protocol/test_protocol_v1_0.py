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
    def test_send_get_protocol_version(self):
        self.assert_req_bytes(self.proto.get_protocol_version(), [1,1,0,0])

    def test_send_get_software_id(self):
        self.assert_req_bytes(self.proto.get_software_id(), [1,2,0,0])

    def test_send_get_supported_features(self):
        self.assert_req_bytes(self.proto.get_supported_features(), [1,3,0,0])

    def test_send_read_memory_block(self):
        self.assert_req_bytes(self.proto.read_memory_block(0x12345678, 0x123), [3,1,0,6, 0x12, 0x34, 0x56, 0x78, 0x1, 0x23])

    def test_send_write_memory_block(self):
        self.assert_req_bytes(self.proto.write_memory_block(0x12345678, bytes([0x11, 0x22, 0x33])), [3,2,0,7, 0x12, 0x34, 0x56, 0x78, 0x11, 0x22, 0x33])

    def test_send_heartbeat(self):
        self.assert_req_bytes(self.proto.ping(), [4,1,0,0])
        self.assert_req_bytes(self.proto.pong(), [4,2,0,0])

    def test_send_datalog_get_targets(self):
        self.assert_req_bytes(self.proto.datalog_get_targets(), [6,1,0,0])

    def test_send_datalog_get_buffer_size(self):
        self.assert_req_bytes(self.proto.datalog_get_bufsize(), [6,2,0,0])

    def test_send_datalog_get_buffer_size(self):
        self.assert_req_bytes(self.proto.datalog_get_sampling_rates(), [6,3,0,0])

    def test_send_datalog_configure_log(self):
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
        self.assert_req_bytes(self.proto.datalog_configure_log(conf), payload)

    def test_send_datalog_list_records(self):
        self.assert_req_bytes(self.proto.datalog_get_list_recording(), [6,5,0,0])

    def test_send_datalog_read_recording(self):
        self.assert_req_bytes(self.proto.datalog_read_recording(record_id = 0x1234), [6,6,0,2, 0x12, 0x34])

    def test_send_datalog_arm_log(self):
        self.assert_req_bytes(self.proto.datalog_arm(), [6,7,0,0])

    def test_send_datalog_disarm_log(self):
        self.assert_req_bytes(self.proto.datalog_disarm(), [6,8,0,0])

    def test_send_datalog_get_log_status(self):
        self.assert_req_bytes(self.proto.datalog_status(), [6,9,0,0])

    

