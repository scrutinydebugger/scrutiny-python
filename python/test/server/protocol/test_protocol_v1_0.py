import unittest
from scrutiny.server.protocol import Protocol
from scrutiny.server.protocol import commands as cmd
from scrutiny.server.protocol.datalog import *
from scrutiny.core import VariableType
import struct

from scrutiny.server.protocol.crc32 import crc32

class TestProtocolV1_0(unittest.TestCase):

    def setUp(self):
        self.proto = Protocol(1, 0)

    def append_crc(self, data):
        return data + struct.pack('>L', crc32(data))

    def assert_req_response_bytes(self, req_response, data):
        self.assertEqual(req_response.to_bytes(), self.append_crc(bytes(data)))

# ============================
#               Request
# ============================

# ============= GetInfo ===============
    def test_req_get_protocol_version(self):
        req = self.proto.get_protocol_version()
        self.assert_req_response_bytes(req, [1,1,0,0])
        data = self.proto.parse_request(req)

    def test_req_get_software_id(self):
        req = self.proto.get_software_id()
        self.assert_req_response_bytes(req, [1,2,0,0])
        data = self.proto.parse_request(req)

    def test_req_get_supported_features(self):
        req = self.proto.get_supported_features()
        self.assert_req_response_bytes(req, [1,3,0,0])
        data = self.proto.parse_request(req)

# ============= MemoryControl ===============

    def test_req_read_memory_block(self):
        req = self.proto.read_memory_block(0x12345678, 0x123)
        self.assert_req_response_bytes(req, [3,1,0,6, 0x12, 0x34, 0x56, 0x78, 0x1, 0x23])
        data = self.proto.parse_request(req)
        self.assertEqual(data['address'], 0x12345678)
        self.assertEqual(data['length'], 0x123)

    def test_req_write_memory_block(self):
        req = self.proto.write_memory_block(0x12345678, bytes([0x11, 0x22, 0x33]))
        self.assert_req_response_bytes(req, [3,2,0,7, 0x12, 0x34, 0x56, 0x78, 0x11, 0x22, 0x33])
        data = self.proto.parse_request(req)
        self.assertEqual(data['address'], 0x12345678)
        self.assertEqual(data['data'], bytes([0x11, 0x22, 0x33]))

# ============= CommControl ===============

    def test_req_comm_discover(self):
        magic = bytes([0x7e, 0x18, 0xfc, 0x68])
        request_bytes = bytes([2,1,0,0x08]) + magic + struct.pack('>L', 0x12345678)
        req = self.proto.comm_discover(0x12345678)
        self.assert_req_response_bytes(req, request_bytes)
        data = self.proto.parse_request(req)
        self.assertEqual(data['magic'], magic)
        self.assertEqual(data['challenge'], 0x12345678)

    def test_req_comm_heartbeat(self):
        req = self.proto.comm_heartbeat(0xAA, 0x1234)
        self.assert_req_response_bytes(req, [2,2,0,3, 0xAA, 0x12, 0x34])
        data = self.proto.parse_request(req)
        self.assertEqual(data['rolling_counter'], 0xAA)
        self.assertEqual(data['challenge'], 0x1234)

# ============= Datalog ===============

    def test_req_datalog_get_targets(self):
        req = self.proto.datalog_get_targets()
        self.assert_req_response_bytes(req, [5,1,0,0])
        data = self.proto.parse_request(req)

    def test_req_datalog_get_buffer_size(self):
        req = self.proto.datalog_get_bufsize()
        self.assert_req_response_bytes(req, [5,2,0,0])
        data = self.proto.parse_request(req)

    def test_req_datalog_get_sampling_rates(self):
        req = self.proto.datalog_get_sampling_rates()
        self.assert_req_response_bytes(req, [5,3,0,0])
        data = self.proto.parse_request(req)

    def test_req_datalog_configure_log(self):
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

        payload = bytes([5,4]) + struct.pack('>H', len(data)) + data
        req = self.proto.datalog_configure_log(conf)
        self.assert_req_response_bytes(req, payload)
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


    def test_req_datalog_list_recordings(self):
        req = self.proto.datalog_get_list_recordings()
        self.assert_req_response_bytes(req, [5,5,0,0])
        data = self.proto.parse_request(req)

    def test_req_datalog_read_recording(self):
        req = self.proto.datalog_read_recording(record_id = 0x1234)
        self.assert_req_response_bytes(req, [5,6,0,2, 0x12, 0x34])
        data = self.proto.parse_request(req)
        self.assertEqual(data['record_id'], 0x1234)

    def test_req_datalog_arm_log(self):
        req = self.proto.datalog_arm()
        self.assert_req_response_bytes(req, [5,7,0,0])
        data = self.proto.parse_request(req)

    def test_req_datalog_disarm_log(self):
        req = self.proto.datalog_disarm()
        self.assert_req_response_bytes(req, [5,8,0,0])
        data = self.proto.parse_request(req)

    def test_req_datalog_get_log_status(self):
        req = self.proto.datalog_status()
        self.assert_req_response_bytes(req, [5,9,0,0])
        data = self.proto.parse_request(req)


# ============= UserCommand ===============

    def test_req_user_command(self):
        req = self.proto.user_command(10, bytes([1,2,3]))
        self.assert_req_response_bytes(req, [4,10,0,3, 1,2,3])
        self.assertEqual(req.subfn, 10)
        self.assertEqual(req.payload, bytes([1,2,3]))



# ============================
#               Response
# ============================

# =============  GetInfo ==============

    def test_response_get_protocol_version(self):
        response = self.proto.respond_protocol_version(major = 2, minor=3)
        self.assert_req_response_bytes(response, [0x81,1,0,0,2,2,3])
        data = self.proto.parse_response(response)
        self.assertEqual(data['major'], 2)
        self.assertEqual(data['minor'], 3)
        response = self.proto.respond_protocol_version()    # Make sure we default to the protocol object version if none is specified
        self.assert_req_response_bytes(response, [0x81,1,0,0,2, self.proto.version_major, self.proto.version_minor])

    def test_response_get_software_id(self):
        response = self.proto.respond_software_id('hello'.encode('ascii'))
        self.assert_req_response_bytes(response, bytes([0x81,2,0,0,5]) + 'hello'.encode('ascii'))
        data = self.proto.parse_response(response)
        self.assertEqual(data['software_id'], 'hello'.encode('ascii'))

    def test_response_get_supported_features(self):
        response = self.proto.respond_supported_features(memory_read=True, memory_write=False, datalog_acquire=True, user_command=True)
        self.assert_req_response_bytes(response, [0x81,3,0,0,1, 0xB0])
        data = self.proto.parse_response(response)
        data['memory_read'] = True
        data['memory_write'] = False
        data['datalog_acquire'] = True
        data['user_command'] = True

# ============= MemoryControl ===============

    def test_response_read_memory_block(self):
        response = self.proto.respond_read_memory_block(0x12345678, bytes([0x11, 0x22, 0x33]))
        self.assert_req_response_bytes(response, [0x83,1,0,0,7, 0x12, 0x34, 0x56, 0x78, 0x11, 0x22, 0x33])
        data = self.proto.parse_response(response)
        self.assertEqual(data['address'], 0x12345678)
        self.assertEqual(data['data'], bytes([0x11, 0x22, 0x33]))

    def test_response_write_memory_block(self):
        response = self.proto.respond_write_memory_block(0x12345678, 3)
        self.assert_req_response_bytes(response, [0x83,2,0, 0, 6, 0x12, 0x34, 0x56, 0x78, 0, 3])
        data = self.proto.parse_response(response)
        self.assertEqual(data['address'], 0x12345678)
        self.assertEqual(data['length'], 3)

# ============= CommControl ===============

    def test_response_comm_discover(self):
        magic = bytes([0x7e, 0x18, 0xfc, 0x68])
        response_bytes = bytes([0x82,1,0,0, 8]) + magic + struct.pack('>L', 0x87654321)
        response = self.proto.respond_comm_discover(0x87654321)
        self.assert_req_response_bytes(response, response_bytes)
        data = self.proto.parse_response(response)
        self.assertEqual(data['magic'], magic)
        self.assertEqual(data['challenge_response'], 0x87654321)

    def test_response_comm_heartbeat(self):
        response = self.proto.respond_comm_heartbeat(0xAA, 0x1234)
        self.assert_req_response_bytes(response, [0x82,2,0,0,3,0xAA, 0x12, 0x34])
        data = self.proto.parse_response(response)
        self.assertEqual(data['rolling_counter'], 0xAA)
        self.assertEqual(data['challenge_response'], 0x1234)
        

# ============= Datalog ===============

    def test_response_datalog_get_targets(self):
        targets = []
        targets.append(DatalogLocation(target_id=0, location_type = DatalogLocation.Type.RAM, name='RAM'))
        targets.append(DatalogLocation(target_id=2, location_type = DatalogLocation.Type.ROM, name='FLASH'))
        targets.append(DatalogLocation(target_id=5, location_type = DatalogLocation.Type.EXTERNAL, name='SD CARD'))


        payload = bytes([0,0,3]) + 'RAM'.encode('ASCII')
        payload += bytes([2,1,5]) + 'FLASH'.encode('ASCII')
        payload += bytes([5,2,7]) + 'SD CARD'.encode('ASCII')

        payload = bytes([0x85,1,0]) + struct.pack('>H', len(payload)) + payload
        response = self.proto.respond_data_get_targets(targets)

        self.assert_req_response_bytes(response, payload)
        data = self.proto.parse_response(response)
        targets = data['targets']
        self.assertEqual(len(targets), 3)
        
        self.assertEqual(targets[0].target_id, 0)
        self.assertEqual(targets[0].name, 'RAM')
        self.assertEqual(targets[0].location_type, DatalogLocation.Type.RAM)

        self.assertEqual(targets[1].target_id, 2)
        self.assertEqual(targets[1].name, 'FLASH')
        self.assertEqual(targets[1].location_type, DatalogLocation.Type.ROM)

        self.assertEqual(targets[2].target_id, 5)
        self.assertEqual(targets[2].name, 'SD CARD')
        self.assertEqual(targets[2].location_type, DatalogLocation.Type.EXTERNAL)

    def test_response_datalog_get_buffer_size(self):
        response = self.proto.respond_datalog_get_bufsize(0x12345678)
        self.assert_req_response_bytes(response, [0x85,2,0,0,4,0x12,0x34,0x56,0x78])
        data = self.proto.parse_response(response)
        self.assertEqual(data['size'], 0x12345678)

    def test_response_datalog_get_sampling_rates(self):
        response = self.proto.respond_datalog_get_sampling_rates([0.1,1,10])
        payload = bytes([0x85,3,0,0,12]) + struct.pack('>fff', 0.1,1,10)
        self.assert_req_response_bytes(response, payload)
        data = self.proto.parse_response(response)
        self.assertEqual(len(data['sampling_rates']), 3)
        self.assertAlmostEqual(data['sampling_rates'][0], 0.1, 5)
        self.assertAlmostEqual(data['sampling_rates'][1], 1, 5)
        self.assertAlmostEqual(data['sampling_rates'][2], 10, 5)

    def test_response_datalog_arm_log(self):
        response = self.proto.respond_datalog_arm(record_id = 0x1234)
        self.assert_req_response_bytes(response, [0x85,7,0,0,2, 0x12, 0x34])
        data = self.proto.parse_response(response)
        self.assertEqual(data['record_id'], 0x1234)

    def test_response_datalog_disarm_log(self):
        response = self.proto.respond_datalog_disarm()
        self.assert_req_response_bytes(response, [0x85,8,0,0,0])
        data = self.proto.parse_response(response)

    def test_response_datalog_get_log_status(self):
        response = self.proto.respond_datalog_status(status=LogStatus.Triggered)
        self.assert_req_response_bytes(response, [0x85,9,0,0,1,1])
        data = self.proto.parse_response(response)
        self.assertEqual(data['status'], LogStatus.Triggered)

    def test_response_datalog_list_records(self):
        recordings = []
        recordings.append(RecordInfo(record_id=0x1234, location_type=DatalogLocation.Type.RAM, size=0x201 ))
        recordings.append(RecordInfo(record_id=0x4567, location_type=DatalogLocation.Type.ROM, size=0x333 ))
        response = self.proto.respond_datalog_list_recordings(recordings)
        self.assert_req_response_bytes(response, [0x85,5,0,0, 10, 0x12, 0x34, 0, 0x02, 0x01, 0x45, 0x67, 1, 0x03, 0x33])
        data = self.proto.parse_response(response)
        self.assertEqual(len(data['recordings']), 2)
        self.assertEqual(data['recordings'][0].record_id, 0x1234)
        self.assertEqual(data['recordings'][0].location_type, DatalogLocation.Type.RAM)
        self.assertEqual(data['recordings'][0].size, 0x201)
        self.assertEqual(data['recordings'][1].record_id, 0x4567)
        self.assertEqual(data['recordings'][1].location_type, DatalogLocation.Type.ROM)
        self.assertEqual(data['recordings'][1].size, 0x333)

    def test_response_datalog_read_recording(self):
        record_data = bytes(range(256))
        response = self.proto.respond_read_recording(record_id=0x1234, data=record_data)
        payload = bytes([0x85,6,0,1,2, 0x12, 0x34])+record_data
        self.assert_req_response_bytes(response, payload)
        data = self.proto.parse_response(response)
        self.assertEqual(data['record_id'], 0x1234)
        self.assertEqual(data['data'], record_data)

    def test_response_datalog_configure_log(self):
        record_data = bytes(range(256))
        response = self.proto.respond_configure_log(record_id=0x1234)
        payload = bytes([0x85,4,0,0,2, 0x12, 0x34])
        self.assert_req_response_bytes(response, payload)
        data = self.proto.parse_response(response)
        self.assertEqual(data['record_id'], 0x1234)

# ============= UserCommand ===============

    def test_response_user_cmd(self):
        response = self.proto.respond_user_command(10, bytes([1,2,3]))
        self.assert_req_response_bytes(response, [0x84,10,0,0,3,1,2,3])
        self.assertEqual(response.subfn, 10)
        self.assertEqual(response.payload, bytes([1,2,3]))

