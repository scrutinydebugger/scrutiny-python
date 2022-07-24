#    test_protocol_v1_0.py
#        Test the Scrutiny Protocol.
#         Validate encoding and decoding of each command.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import unittest
from scrutiny.server.protocol import Protocol, Response, Request
from scrutiny.server.protocol import commands as cmd
from scrutiny.server.protocol.datalog import *
from scrutiny.core import VariableType
import struct

from scrutiny.server.protocol.crc32 import crc32


class TestProtocolV1_0(unittest.TestCase):

    def setUp(self):
        self.proto = Protocol(1, 0, address_size_bits=32)

    def append_crc(self, data):
        return data + struct.pack('>L', crc32(data))

    def assert_req_response_bytes(self, req_response, data):
        self.assertEqual(req_response.to_bytes(), self.append_crc(bytes(data)))

    def test_compute_challenge_16bits(self):
        self.assertEqual(self.proto.compute_challenge_16bits(0), 0xFFFF)
        self.assertEqual(self.proto.compute_challenge_16bits(0xFFFF), 0)
        self.assertEqual(self.proto.compute_challenge_16bits(0x10000), 0xFFFF)
        self.assertEqual(self.proto.compute_challenge_16bits(0x1234), 0xEDCB)
        self.assertEqual(self.proto.compute_challenge_16bits(0xEDCB), 0x1234)

    def test_compute_challenge_32bits(self):
        self.assertEqual(self.proto.compute_challenge_32bits(0), 0xFFFFFFFF)
        self.assertEqual(self.proto.compute_challenge_32bits(0), 0xFFFFFFFF)
        self.assertEqual(self.proto.compute_challenge_32bits(0xFFFF), 0xFFFF0000)
        self.assertEqual(self.proto.compute_challenge_32bits(0xFFFF0000), 0xFFFF)
        self.assertEqual(self.proto.compute_challenge_32bits(0x100000000), 0xFFFFFFFF)
        self.assertEqual(self.proto.compute_challenge_32bits(0x12345678), 0xEDCBA987)
        self.assertEqual(self.proto.compute_challenge_32bits(0xEDCBA987), 0x12345678)

    def check_expected_payload_size(self, req, size):
        self.assertEqual(req.get_expected_response_size(), 9 + size)

# ============================
#               Request
# ============================

# ============= GetInfo ===============
    def test_req_get_protocol_version(self):
        req = self.proto.get_protocol_version()
        self.assert_req_response_bytes(req, [1, 1, 0, 0])
        data = self.proto.parse_request(req)
        self.check_expected_payload_size(req, 2)

    def test_req_get_software_id(self):
        req = self.proto.get_software_id()
        self.assert_req_response_bytes(req, [1, 2, 0, 0])
        data = self.proto.parse_request(req)
        self.check_expected_payload_size(req, 32)

    def test_req_get_supported_features(self):
        req = self.proto.get_supported_features()
        self.assert_req_response_bytes(req, [1, 3, 0, 0])
        data = self.proto.parse_request(req)
        self.check_expected_payload_size(req, 1)

    def test_req_get_special_memory_range_count(self):
        req = self.proto.get_special_memory_region_count()
        self.assert_req_response_bytes(req, [1, 4, 0, 0])
        data = self.proto.parse_request(req)
        self.check_expected_payload_size(req, 2)

    def test_req_get_special_memory_range_location(self):
        req = self.proto.get_special_memory_region_location(cmd.GetInfo.MemoryRangeType.Forbidden, 0x12)
        self.assert_req_response_bytes(req, [1, 5, 0, 2, 1, 0x12])
        data = self.proto.parse_request(req)
        self.assertEqual(data['region_type'], cmd.GetInfo.MemoryRangeType.Forbidden)
        self.assertEqual(data['region_index'], 0x12)
        self.check_expected_payload_size(req, 2 + self.proto.get_address_size_bytes() * 2)
    
    def test_req_get_rpv_count(self):
        req = self.proto.get_rpv_count()
        self.assert_req_response_bytes(req, [1, 6, 0, 0])
        data = self.proto.parse_request(req)
        self.check_expected_payload_size(req, 2)
    
    def test_req_get_rpv_definition(self):
        req = self.proto.get_rpv_definition(start=2, count=5)
        self.assert_req_response_bytes(req, [1, 7, 0, 4, 0, 2, 0, 5])
        data = self.proto.parse_request(req)
        self.assertEqual(data['start'], 2)
        self.assertEqual(data['count'], 5)
        self.check_expected_payload_size(req, 4*5)

# ============= MemoryControl ===============
    def test_req_read_single_memory_block_8bits(self):
        self.proto.set_address_size_bits(8)
        req = self.proto.read_single_memory_block(0x99, 0x123)
        self.assert_req_response_bytes(req, [3, 1, 0, 3, 0x99, 0x01, 0x23])
        data = self.proto.parse_request(req)
        self.assertEqual(data['blocks_to_read'][0]['address'], 0x99)
        self.assertEqual(data['blocks_to_read'][0]['length'], 0x123)
        self.check_expected_payload_size(req, 1 + 2 + 0x123)    # address+data_Size+data

    def test_req_read_multiple_memory_block_8bits(self):
        self.proto.set_address_size_bits(8)
        req = self.proto.read_memory_blocks([(0x99, 0x123), (0x88, 0x456)])
        self.assert_req_response_bytes(req, [3, 1, 0, 6, 0x99, 0x1, 0x23, 0x88, 0x04, 0x56])
        data = self.proto.parse_request(req)
        self.assertEqual(data['blocks_to_read'][0]['address'], 0x99)
        self.assertEqual(data['blocks_to_read'][0]['length'], 0x123)
        self.assertEqual(data['blocks_to_read'][1]['address'], 0x88)
        self.assertEqual(data['blocks_to_read'][1]['length'], 0x456)
        self.check_expected_payload_size(req, 1 * 2 + 2 * 2 + 0x123 + 0x456)    # address*2+data_Size*2+data

    def test_req_read_single_memory_block_16bits(self):
        self.proto.set_address_size_bits(16)
        req = self.proto.read_single_memory_block(0x1234, 0x123)
        self.assert_req_response_bytes(req, [3, 1, 0, 4, 0x12, 0x34, 0x01, 0x23])
        data = self.proto.parse_request(req)
        self.assertEqual(data['blocks_to_read'][0]['address'], 0x1234)
        self.assertEqual(data['blocks_to_read'][0]['length'], 0x123)
        self.check_expected_payload_size(req, 2 + 2 + 0x123)    # address*2+data_Size*2+data

    def test_req_read_multiple_memory_block_16bits(self):
        self.proto.set_address_size_bits(16)
        req = self.proto.read_memory_blocks([(0x1234, 0x123), (0x1122, 0x456)])
        self.assert_req_response_bytes(req, [3, 1, 0, 8, 0x12, 0x34, 0x1, 0x23, 0x11, 0x22, 0x04, 0x56])
        data = self.proto.parse_request(req)
        self.assertEqual(data['blocks_to_read'][0]['address'], 0x1234)
        self.assertEqual(data['blocks_to_read'][0]['length'], 0x123)
        self.assertEqual(data['blocks_to_read'][1]['address'], 0x1122)
        self.assertEqual(data['blocks_to_read'][1]['length'], 0x456)
        self.check_expected_payload_size(req, 2 * 2 + 2 * 2 + 0x123 + 0x456)    # address*2+data_Size*2+data

    def test_req_read_single_memory_block_32bits(self):
        self.proto.set_address_size_bits(32)
        req = self.proto.read_single_memory_block(0x12345678, 0x123)
        self.assert_req_response_bytes(req, [3, 1, 0, 6, 0x12, 0x34, 0x56, 0x78, 0x1, 0x23])
        data = self.proto.parse_request(req)
        self.assertEqual(data['blocks_to_read'][0]['address'], 0x12345678)
        self.assertEqual(data['blocks_to_read'][0]['length'], 0x123)
        self.check_expected_payload_size(req, 4 + 2 + 0x123)    # address*2+data_Size*2+data

    def test_req_read_multiple_memory_block_32bits(self):
        self.proto.set_address_size_bits(32)
        req = self.proto.read_memory_blocks([(0x12345678, 0x123), (0x11223344, 0x456)])
        self.assert_req_response_bytes(req, [3, 1, 0, 12, 0x12, 0x34, 0x56, 0x78, 0x1, 0x23, 0x11, 0x22, 0x33, 0x44, 0x04, 0x56])
        data = self.proto.parse_request(req)
        self.assertEqual(data['blocks_to_read'][0]['address'], 0x12345678)
        self.assertEqual(data['blocks_to_read'][0]['length'], 0x123)
        self.assertEqual(data['blocks_to_read'][1]['address'], 0x11223344)
        self.assertEqual(data['blocks_to_read'][1]['length'], 0x456)
        self.check_expected_payload_size(req, 4 * 2 + 2 * 2 + 0x123 + 0x456)    # address*2+data_Size*2+data

    def test_req_read_single_memory_block_64bits(self):
        self.proto.set_address_size_bits(64)
        req = self.proto.read_single_memory_block(0x123456789ABCDEF0, 0x123)
        self.assert_req_response_bytes(req, [3, 1, 0, 10, 0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0, 0x1, 0x23])
        data = self.proto.parse_request(req)
        self.assertEqual(data['blocks_to_read'][0]['address'], 0x123456789ABCDEF0)
        self.assertEqual(data['blocks_to_read'][0]['length'], 0x123)
        self.check_expected_payload_size(req, 8 + 2 + 0x123)    # address*2+data_Size*2+data

    def test_req_read_multiple_memory_block_64bits(self):
        self.proto.set_address_size_bits(64)
        req = self.proto.read_memory_blocks([(0x123456789ABCDEF0, 0x123), (0x1122334455667788, 0x456)])
        self.assert_req_response_bytes(req, [3, 1, 0, 20, 0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0,
                                       0x1, 0x23, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x04, 0x56])
        data = self.proto.parse_request(req)
        self.assertEqual(data['blocks_to_read'][0]['address'], 0x123456789ABCDEF0)
        self.assertEqual(data['blocks_to_read'][0]['length'], 0x123)
        self.assertEqual(data['blocks_to_read'][1]['address'], 0x1122334455667788)
        self.assertEqual(data['blocks_to_read'][1]['length'], 0x456)
        self.check_expected_payload_size(req, 8 * 2 + 2 * 2 + 0x123 + 0x456)    # address*2+data_size*2+data

    def test_req_read_single_memory_block_32bits_bad_content(self):
        self.proto.logger.disabled = True
        self.proto.set_address_size_bits(32)
        request = Request(cmd.MemoryControl, cmd.MemoryControl.Subfunction.Read, [0x12, 0x34, 0x56, 0x78, 0x01])
        with self.assertRaises(Exception):
            self.proto.logger.disabled = True
            self.proto.parse_request(request)

        request = Request(cmd.MemoryControl, cmd.MemoryControl.Subfunction.Read, [0x12, 0x34, 0x56, 0x78, 0x01, 0x23, 0x45])
        with self.assertRaises(Exception):
            self.proto.logger.disabled = True
            self.proto.parse_request(request)

# ----------

    def test_req_write_single_memory_block_8bits(self):
        self.proto.set_address_size_bits(8)
        req = self.proto.write_single_memory_block(0x12, bytes([0x11, 0x22, 0x33]))
        self.assert_req_response_bytes(req, [3, 2, 0, 6, 0x12, 0x00, 0x03, 0x11, 0x22, 0x33])
        data = self.proto.parse_request(req)
        self.assertEqual(data['blocks_to_write'][0]['address'], 0x12)
        self.assertEqual(data['blocks_to_write'][0]['data'], bytes([0x11, 0x22, 0x33]))
        self.check_expected_payload_size(req, 1 + 2)    # address+data_size

    def test_req_write_single_memory_block_8bits_masked(self):
        self.proto.set_address_size_bits(8)
        req = self.proto.write_single_memory_block(0x12, bytes([0x11, 0x22, 0x33]), bytes([0xFF, 0xAA, 0x55]))
        self.assert_req_response_bytes(req, [3, 3, 0, 9, 0x12, 0x00, 0x03, 0x11, 0x22, 0x33, 0xFF, 0xAA, 0x55])
        data = self.proto.parse_request(req)
        self.assertEqual(data['blocks_to_write'][0]['address'], 0x12)
        self.assertEqual(data['blocks_to_write'][0]['data'], bytes([0x11, 0x22, 0x33]))
        self.assertEqual(data['blocks_to_write'][0]['write_mask'], bytes([0xFF, 0xAA, 0x55]))
        self.check_expected_payload_size(req, 1 + 2)    # address+data_size

    def test_req_write_multiple_memory_block_8bits(self):
        self.proto.set_address_size_bits(8)
        blocks = []
        blocks.append((0x12, bytes([0x11, 0x22, 0x33])))
        blocks.append((0x34, bytes([0x99, 0x88, 0x77, 0x66])))
        req = self.proto.write_memory_blocks(blocks)
        self.assert_req_response_bytes(req, [3, 2, 0, 13, 0x12, 0x00, 0x03, 0x11, 0x22, 0x33, 0x34, 0x00, 0x04, 0x99, 0x88, 0x77, 0x66])
        data = self.proto.parse_request(req)
        self.assertEqual(data['blocks_to_write'][0]['address'], 0x12)
        self.assertEqual(data['blocks_to_write'][0]['data'], bytes([0x11, 0x22, 0x33]))
        self.assertEqual(data['blocks_to_write'][1]['address'], 0x34)
        self.assertEqual(data['blocks_to_write'][1]['data'], bytes([0x99, 0x88, 0x77, 0x66]))
        self.check_expected_payload_size(req, 1 * 2 + 2 * 2)    # address+data_size

    def test_req_write_multiple_memory_block_8bits_masked(self):
        self.proto.set_address_size_bits(8)
        blocks = []
        blocks.append((0x12, bytes([0x11, 0x22, 0x33]), bytes([0x99, 0x88, 0x77])))
        blocks.append((0x34, bytes([0x99, 0x88, 0x77, 0x66]), bytes([0x01, 0x02, 0x04, 0x08])))
        req = self.proto.write_memory_blocks_masked(blocks)
        self.assert_req_response_bytes(req, [3, 3, 0, 20, 0x12, 0x00, 0x03, 0x11, 0x22, 0x33, 0x99, 0x88,
                                       0x77, 0x34, 0x00, 0x04, 0x99, 0x88, 0x77, 0x66, 0x01, 0x02, 0x04, 0x08])
        data = self.proto.parse_request(req)
        self.assertEqual(data['blocks_to_write'][0]['address'], 0x12)
        self.assertEqual(data['blocks_to_write'][0]['data'], bytes([0x11, 0x22, 0x33]))
        self.assertEqual(data['blocks_to_write'][0]['write_mask'], bytes([0x99, 0x88, 0x77]))
        self.assertEqual(data['blocks_to_write'][1]['address'], 0x34)
        self.assertEqual(data['blocks_to_write'][1]['data'], bytes([0x99, 0x88, 0x77, 0x66]))
        self.assertEqual(data['blocks_to_write'][1]['write_mask'], bytes([0x01, 0x02, 0x04, 0x08]))
        self.check_expected_payload_size(req, 1 * 2 + 2 * 2)    # address+data_size

    def test_req_write_single_memory_block_16bits(self):
        self.proto.set_address_size_bits(16)
        req = self.proto.write_single_memory_block(0x1234, bytes([0x11, 0x22, 0x33]))
        self.assert_req_response_bytes(req, [3, 2, 0, 7, 0x12, 0x34, 0x00, 0x03, 0x11, 0x22, 0x33])
        data = self.proto.parse_request(req)
        self.assertEqual(data['blocks_to_write'][0]['address'], 0x1234)
        self.assertEqual(data['blocks_to_write'][0]['data'], bytes([0x11, 0x22, 0x33]))
        self.check_expected_payload_size(req, 2 + 2)    # address+data_size

    def test_req_write_single_memory_block_16bits_masked(self):
        self.proto.set_address_size_bits(16)
        req = self.proto.write_single_memory_block(0x1234, bytes([0x11, 0x22, 0x33]), bytes([0xFF, 0xAA, 0x55]))
        self.assert_req_response_bytes(req, [3, 3, 0, 10, 0x12, 0x34, 0x00, 0x03, 0x11, 0x22, 0x33, 0xFF, 0xAA, 0x55])
        data = self.proto.parse_request(req)
        self.assertEqual(data['blocks_to_write'][0]['address'], 0x1234)
        self.assertEqual(data['blocks_to_write'][0]['data'], bytes([0x11, 0x22, 0x33]))
        self.assertEqual(data['blocks_to_write'][0]['write_mask'], bytes([0xFF, 0xAA, 0x55]))
        self.check_expected_payload_size(req, 2 + 2)    # address+data_size

    def test_req_write_multiple_memory_block_16bits(self):
        self.proto.set_address_size_bits(16)
        blocks = []
        blocks.append((0x1234, bytes([0x11, 0x22, 0x33])))
        blocks.append((0x5678, bytes([0x99, 0x88, 0x77, 0x66])))
        req = self.proto.write_memory_blocks(blocks)
        self.assert_req_response_bytes(req, [3, 2, 0, 15, 0x12, 0x34, 0x00, 0x03, 0x11, 0x22, 0x33, 0x56, 0x78, 0x00, 0x04, 0x99, 0x88, 0x77, 0x66])
        data = self.proto.parse_request(req)
        self.assertEqual(data['blocks_to_write'][0]['address'], 0x1234)
        self.assertEqual(data['blocks_to_write'][0]['data'], bytes([0x11, 0x22, 0x33]))
        self.assertEqual(data['blocks_to_write'][1]['address'], 0x5678)
        self.assertEqual(data['blocks_to_write'][1]['data'], bytes([0x99, 0x88, 0x77, 0x66]))
        self.check_expected_payload_size(req, 2 * 2 + 2 * 2)    # address+data_size

    def test_req_write_multiple_memory_block_16bits_masked(self):
        self.proto.set_address_size_bits(16)
        blocks = []
        blocks.append((0x1234, bytes([0x11, 0x22, 0x33]), bytes([0x99, 0x88, 0x77])))
        blocks.append((0x5678, bytes([0x99, 0x88, 0x77, 0x66]), bytes([0x01, 0x02, 0x04, 0x08])))
        req = self.proto.write_memory_blocks_masked(blocks)
        self.assert_req_response_bytes(req, [3, 3, 0, 22, 0x12, 0x34, 0x00, 0x03, 0x11, 0x22, 0x33, 0x99, 0x88,
                                       0x77, 0x56, 0x78, 0x00, 0x04, 0x99, 0x88, 0x77, 0x66, 0x01, 0x02, 0x04, 0x08])
        data = self.proto.parse_request(req)
        self.assertEqual(data['blocks_to_write'][0]['address'], 0x1234)
        self.assertEqual(data['blocks_to_write'][0]['data'], bytes([0x11, 0x22, 0x33]))
        self.assertEqual(data['blocks_to_write'][0]['write_mask'], bytes([0x99, 0x88, 0x77]))
        self.assertEqual(data['blocks_to_write'][1]['address'], 0x5678)
        self.assertEqual(data['blocks_to_write'][1]['data'], bytes([0x99, 0x88, 0x77, 0x66]))
        self.assertEqual(data['blocks_to_write'][1]['write_mask'], bytes([0x01, 0x02, 0x04, 0x08]))
        self.check_expected_payload_size(req, 2 * 2 + 2 * 2)    # address+data_size

    def test_req_write_single_memory_block_32bits(self):
        self.proto.set_address_size_bits(32)
        req = self.proto.write_single_memory_block(0x12345678, bytes([0x11, 0x22, 0x33]))
        self.assert_req_response_bytes(req, [3, 2, 0, 9, 0x12, 0x34, 0x56, 0x78, 0x00, 0x03, 0x11, 0x22, 0x33])
        data = self.proto.parse_request(req)
        self.assertEqual(data['blocks_to_write'][0]['address'], 0x12345678)
        self.assertEqual(data['blocks_to_write'][0]['data'], bytes([0x11, 0x22, 0x33]))
        self.check_expected_payload_size(req, 4 + 2)    # address+data_size

    def test_req_write_single_memory_block_32bits_masked(self):
        self.proto.set_address_size_bits(32)
        req = self.proto.write_single_memory_block(0x12345678, bytes([0x11, 0x22, 0x33]), bytes([0xFF, 0xAA, 0x55]))
        self.assert_req_response_bytes(req, [3, 3, 0, 12, 0x12, 0x34, 0x56, 0x78, 0x00, 0x03, 0x11, 0x22, 0x33, 0xFF, 0xAA, 0x55])
        data = self.proto.parse_request(req)
        self.assertEqual(data['blocks_to_write'][0]['address'], 0x12345678)
        self.assertEqual(data['blocks_to_write'][0]['data'], bytes([0x11, 0x22, 0x33]))
        self.assertEqual(data['blocks_to_write'][0]['write_mask'], bytes([0xFF, 0xAA, 0x55]))
        self.check_expected_payload_size(req, 4 + 2)    # address+data_size

    def test_req_write_multiple_memory_block_32bits(self):
        self.proto.set_address_size_bits(32)
        blocks = []
        blocks.append((0x12345678, bytes([0x11, 0x22, 0x33])))
        blocks.append((0xFFEEDDCC, bytes([0x99, 0x88, 0x77, 0x66])))
        req = self.proto.write_memory_blocks(blocks)
        self.assert_req_response_bytes(req, [3, 2, 0, 19, 0x12, 0x34, 0x56, 0x78, 0x00, 0x03, 0x11, 0x22,
                                       0x33, 0xFF, 0xEE, 0xDD, 0xCC, 0x00, 0x04, 0x99, 0x88, 0x77, 0x66])
        data = self.proto.parse_request(req)
        self.assertEqual(data['blocks_to_write'][0]['address'], 0x12345678)
        self.assertEqual(data['blocks_to_write'][0]['data'], bytes([0x11, 0x22, 0x33]))
        self.assertEqual(data['blocks_to_write'][1]['address'], 0xFFEEDDCC)
        self.assertEqual(data['blocks_to_write'][1]['data'], bytes([0x99, 0x88, 0x77, 0x66]))
        self.check_expected_payload_size(req, 4 * 2 + 2 * 2)    # address+data_size

    def test_req_write_multiple_memory_block_32bits_masked(self):
        self.proto.set_address_size_bits(32)
        blocks = []
        blocks.append((0x12345678, bytes([0x11, 0x22, 0x33]), bytes([0x99, 0x88, 0x77])))
        blocks.append((0xFFEEDDCC, bytes([0x99, 0x88, 0x77, 0x66]), bytes([0x01, 0x02, 0x04, 0x08])))
        req = self.proto.write_memory_blocks_masked(blocks)
        self.assert_req_response_bytes(req, [3, 3, 0, 26, 0x12, 0x34, 0x56, 0x78, 0x00, 0x03, 0x11, 0x22, 0x33,
                                       0x99, 0x88, 0x77, 0xFF, 0xEE, 0xDD, 0xCC, 0x00, 0x04, 0x99, 0x88, 0x77, 0x66, 0x01, 0x02, 0x04, 0x08])
        data = self.proto.parse_request(req)
        self.assertEqual(data['blocks_to_write'][0]['address'], 0x12345678)
        self.assertEqual(data['blocks_to_write'][0]['data'], bytes([0x11, 0x22, 0x33]))
        self.assertEqual(data['blocks_to_write'][0]['write_mask'], bytes([0x99, 0x88, 0x77]))
        self.assertEqual(data['blocks_to_write'][1]['address'], 0xFFEEDDCC)
        self.assertEqual(data['blocks_to_write'][1]['data'], bytes([0x99, 0x88, 0x77, 0x66]))
        self.assertEqual(data['blocks_to_write'][1]['write_mask'], bytes([0x01, 0x02, 0x04, 0x08]))
        self.check_expected_payload_size(req, 4 * 2 + 2 * 2)    # address+data_size

    def test_req_write_single_memory_block_64bits(self):
        self.proto.set_address_size_bits(64)
        req = self.proto.write_single_memory_block(0x123456789abcdef0, bytes([0x11, 0x22, 0x33]))
        self.assert_req_response_bytes(req, [3, 2, 0, 13, 0x12, 0x34, 0x56, 0x78, 0x9a, 0xbc, 0xde, 0xf0, 0x00, 0x03, 0x11, 0x22, 0x33])
        data = self.proto.parse_request(req)
        self.assertEqual(data['blocks_to_write'][0]['address'], 0x123456789abcdef0)
        self.assertEqual(data['blocks_to_write'][0]['data'], bytes([0x11, 0x22, 0x33]))
        self.check_expected_payload_size(req, 8 + 2)    # address+data_size

    def test_req_write_single_memory_block_64bits_masked(self):
        self.proto.set_address_size_bits(64)
        req = self.proto.write_single_memory_block(0x123456789abcdef0, bytes([0x11, 0x22, 0x33]), bytes([0xFF, 0xAA, 0x55]))
        self.assert_req_response_bytes(req, [3, 3, 0, 16, 0x12, 0x34, 0x56, 0x78, 0x9a, 0xbc,
                                       0xde, 0xf0, 0x00, 0x03, 0x11, 0x22, 0x33, 0xFF, 0xAA, 0x55])
        data = self.proto.parse_request(req)
        self.assertEqual(data['blocks_to_write'][0]['address'], 0x123456789abcdef0)
        self.assertEqual(data['blocks_to_write'][0]['data'], bytes([0x11, 0x22, 0x33]))
        self.assertEqual(data['blocks_to_write'][0]['write_mask'], bytes([0xFF, 0xAA, 0x55]))
        self.check_expected_payload_size(req, 8 + 2)    # address+data_size

    def test_req_write_multiple_memory_block_64bits(self):
        self.proto.set_address_size_bits(64)
        blocks = []
        blocks.append((0x123456789abcdef0, bytes([0x11, 0x22, 0x33])))
        blocks.append((0xfedcba9876543210, bytes([0x99, 0x88, 0x77, 0x66])))
        req = self.proto.write_memory_blocks(blocks)
        self.assert_req_response_bytes(req, [3, 2, 0, 27, 0x12, 0x34, 0x56, 0x78, 0x9a, 0xbc, 0xde, 0xf0, 0x00, 0x03,
                                       0x11, 0x22, 0x33, 0xFE, 0xDC, 0xBA, 0x98, 0x76, 0x54, 0x32, 0x10, 0x00, 0x04, 0x99, 0x88, 0x77, 0x66])
        data = self.proto.parse_request(req)
        self.assertEqual(data['blocks_to_write'][0]['address'], 0x123456789abcdef0)
        self.assertEqual(data['blocks_to_write'][0]['data'], bytes([0x11, 0x22, 0x33]))
        self.assertEqual(data['blocks_to_write'][1]['address'], 0xfedcba9876543210)
        self.assertEqual(data['blocks_to_write'][1]['data'], bytes([0x99, 0x88, 0x77, 0x66]))
        self.check_expected_payload_size(req, 8 * 2 + 2 * 2)    # address+data_size

    def test_req_write_multiple_memory_block_64bits_masked(self):
        self.proto.set_address_size_bits(64)
        blocks = []
        blocks.append((0x123456789abcdef0, bytes([0x11, 0x22, 0x33]), bytes([0x99, 0x88, 0x77])))
        blocks.append((0xfedcba9876543210, bytes([0x99, 0x88, 0x77, 0x66]), bytes([0x01, 0x02, 0x04, 0x08])))
        req = self.proto.write_memory_blocks_masked(blocks)
        self.assert_req_response_bytes(req, [3, 3, 0, 34, 0x12, 0x34, 0x56, 0x78, 0x9a, 0xbc, 0xde, 0xf0, 0x00, 0x03, 0x11, 0x22, 0x33,
                                       0x99, 0x88, 0x77, 0xFE, 0xDC, 0xBA, 0x98, 0x76, 0x54, 0x32, 0x10, 0x00, 0x04, 0x99, 0x88, 0x77, 0x66, 0x01, 0x02, 0x04, 0x08])
        data = self.proto.parse_request(req)
        self.assertEqual(data['blocks_to_write'][0]['address'], 0x123456789abcdef0)
        self.assertEqual(data['blocks_to_write'][0]['data'], bytes([0x11, 0x22, 0x33]))
        self.assertEqual(data['blocks_to_write'][0]['write_mask'], bytes([0x99, 0x88, 0x77]))
        self.assertEqual(data['blocks_to_write'][1]['address'], 0xfedcba9876543210)
        self.assertEqual(data['blocks_to_write'][1]['data'], bytes([0x99, 0x88, 0x77, 0x66]))
        self.assertEqual(data['blocks_to_write'][1]['write_mask'], bytes([0x01, 0x02, 0x04, 0x08]))
        self.check_expected_payload_size(req, 8 * 2 + 2 * 2)    # address+data_size

    def test_req_write_single_memory_block_32bits_bad_content(self):
        self.proto.logger.disabled = True
        self.proto.set_address_size_bits(32)
        request = Request(cmd.MemoryControl, cmd.MemoryControl.Subfunction.Write, [0x12, 0x34, 0x56, 0x78, 0x00, 0x03, 0x11, 0x22])
        with self.assertRaises(Exception):
            self.proto.parse_request(request)

        request = Request(cmd.MemoryControl, cmd.MemoryControl.Subfunction.Write, [0x12, 0x34, 0x56, 0x78, 0x00, 0x03, 0x11, 0x22, 0x33, 0x44])
        with self.assertRaises(Exception):
            self.proto.parse_request(request)

        request = Request(cmd.MemoryControl, cmd.MemoryControl.Subfunction.Write, [0x12, 0x34, 0x56, 0x78, 0x00])
        with self.assertRaises(Exception):
            self.proto.parse_request(request)

        request = Request(cmd.MemoryControl, cmd.MemoryControl.Subfunction.WriteMasked, [0x12, 0x34, 0x56, 0x78, 0x00, 0x01, 0xAA])
        with self.assertRaises(Exception):
            self.proto.parse_request(request)

# ============= CommControl ===============

    def test_req_comm_discover(self):
        magic = bytes([0x7e, 0x18, 0xfc, 0x68])
        request_bytes = bytes([2, 1, 0, 4]) + magic
        req = self.proto.comm_discover()
        self.assert_req_response_bytes(req, request_bytes)
        data = self.proto.parse_request(req)
        self.assertEqual(data['magic'], magic)
        self.check_expected_payload_size(req, 16)    # firmwareid - Response to discover is variable size but 32 bytes at least.

    def test_req_comm_heartbeat(self):
        req = self.proto.comm_heartbeat(0x12345678, 0x1122)
        self.assert_req_response_bytes(req, [2, 2, 0, 6, 0x12, 0x34, 0x56, 0x78, 0x11, 0x22])
        data = self.proto.parse_request(req)
        self.assertEqual(data['session_id'], 0x12345678)
        self.assertEqual(data['challenge'], 0x1122)
        self.check_expected_payload_size(req, 4 + 2)  # session_id  +16bits challenge

    def test_req_comm_get_params(self):
        req = self.proto.comm_get_params()
        self.assert_req_response_bytes(req, [2, 3, 0, 0])
        data = self.proto.parse_request(req)
        # Rx_buffer_size, tx_buffer_size, bitrate, heartbeat_timeout, rx_timeout, address_size
        self.check_expected_payload_size(req, 2 + 2 + 4 + 4 + 4 + 1)

    def test_req_comm_connect(self):
        magic = bytes([0x82, 0x90, 0x22, 0x66])
        request_bytes = bytes([2, 4, 0, 4]) + magic
        req = self.proto.comm_connect()
        self.assert_req_response_bytes(req, request_bytes)
        data = self.proto.parse_request(req)
        self.check_expected_payload_size(req, 4 + 4)  # Magic + Session id

    def test_req_comm_disonnect(self):
        request_bytes = bytes([2, 5, 0, 4]) + struct.pack('>L', 0x12345678)
        req = self.proto.comm_disconnect(0x12345678)
        self.assert_req_response_bytes(req, request_bytes)
        data = self.proto.parse_request(req)
        data['session_id'] = 0x12345678
        self.check_expected_payload_size(req, 0)  # No data

# ============= Datalog ===============

    def test_req_datalog_get_targets(self):
        req = self.proto.datalog_get_targets()
        self.assert_req_response_bytes(req, [5, 1, 0, 0])
        data = self.proto.parse_request(req)
        # todo : Response size

    def test_req_datalog_get_buffer_size(self):
        req = self.proto.datalog_get_bufsize()
        self.assert_req_response_bytes(req, [5, 2, 0, 0])
        data = self.proto.parse_request(req)
        # todo : Response size

    def test_req_datalog_get_sampling_rates(self):
        req = self.proto.datalog_get_sampling_rates()
        self.assert_req_response_bytes(req, [5, 3, 0, 0])
        data = self.proto.parse_request(req)
        # todo : Response size

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
        data += struct.pack('>LHLHLH', 0x1234, 2, 0x1111, 4, 0x2222, 4)  # watch def
        data += b'\x00'  # condition
        data += struct.pack('>BLBB', 2, 0x99887766, 4, 22)  # operand type, operand data
        data += struct.pack('>Bf', 1, 666)  # operand type, operand data

        payload = bytes([5, 4]) + struct.pack('>H', len(data)) + data
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
        self.assertEqual(conf.trigger.condition, conf2.trigger.condition)
        self.assertIsInstance(conf.trigger.operand1, DatalogConfiguration.WatchOperand)
        self.assertEqual(conf.trigger.operand1.address, conf2.trigger.operand1.address)
        self.assertEqual(conf.trigger.operand1.length, conf2.trigger.operand1.length)
        self.assertEqual(conf.trigger.operand1.interpret_as, conf2.trigger.operand1.interpret_as)
        self.assertIsInstance(conf.trigger.operand2, DatalogConfiguration.ConstOperand)
        self.assertEqual(conf.trigger.operand2.value, conf2.trigger.operand2.value)

        # todo : Response size

    def test_req_datalog_list_recordings(self):
        req = self.proto.datalog_get_list_recordings()
        self.assert_req_response_bytes(req, [5, 5, 0, 0])
        data = self.proto.parse_request(req)
        # todo : Response size

    def test_req_datalog_read_recording(self):
        req = self.proto.datalog_read_recording(record_id=0x1234)
        self.assert_req_response_bytes(req, [5, 6, 0, 2, 0x12, 0x34])
        data = self.proto.parse_request(req)
        self.assertEqual(data['record_id'], 0x1234)
        # todo : Response size

    def test_req_datalog_arm_log(self):
        req = self.proto.datalog_arm()
        self.assert_req_response_bytes(req, [5, 7, 0, 0])
        data = self.proto.parse_request(req)
        # todo : Response size

    def test_req_datalog_disarm_log(self):
        req = self.proto.datalog_disarm()
        self.assert_req_response_bytes(req, [5, 8, 0, 0])
        data = self.proto.parse_request(req)
        # todo : Response size

    def test_req_datalog_get_log_status(self):
        req = self.proto.datalog_status()
        self.assert_req_response_bytes(req, [5, 9, 0, 0])
        data = self.proto.parse_request(req)


# ============= UserCommand ===============

    def test_req_user_command(self):
        req = self.proto.user_command(10, bytes([1, 2, 3]))
        self.assert_req_response_bytes(req, [4, 10, 0, 3, 1, 2, 3])
        self.assertEqual(req.subfn, 10)
        self.assertEqual(req.payload, bytes([1, 2, 3]))
        # todo : Response size


# ============================
#               Response
# ============================

# =============  GetInfo ==============

    def test_response_get_protocol_version(self):
        response = self.proto.respond_protocol_version(major=2, minor=3)
        self.assert_req_response_bytes(response, [0x81, 1, 0, 0, 2, 2, 3])
        data = self.proto.parse_response(response)
        self.assertEqual(data['major'], 2)
        self.assertEqual(data['minor'], 3)
        response = self.proto.respond_protocol_version()    # Make sure we default to the protocol object version if none is specified
        self.assert_req_response_bytes(response, [0x81, 1, 0, 0, 2, self.proto.version_major, self.proto.version_minor])

    def test_response_get_software_id(self):
        response = self.proto.respond_software_id('hello'.encode('ascii'))
        self.assert_req_response_bytes(response, bytes([0x81, 2, 0, 0, 5]) + 'hello'.encode('ascii'))
        data = self.proto.parse_response(response)
        self.assertEqual(data['software_id'], 'hello'.encode('ascii'))

    def test_response_get_supported_features(self):
        response = self.proto.respond_supported_features(memory_write=True, datalog_acquire=False, user_command=True)
        self.assert_req_response_bytes(response, [0x81, 3, 0, 0, 1, 0xA0])
        data = self.proto.parse_response(response)
        self.assertEqual(data['memory_write'], True)
        self.assertEqual(data['datalog_acquire'], False)
        self.assertEqual(data['user_command'], True)

    def test_response_get_special_memory_range_count(self):
        response = self.proto.respond_special_memory_region_count(readonly=0xAA, forbidden=0x55)
        self.assert_req_response_bytes(response, [0x81, 4, 0, 0, 2, 0xAA, 0x55])
        data = self.proto.parse_response(response)
        self.assertEqual(data['nbr_readonly'], 0xAA)
        self.assertEqual(data['nbr_forbidden'], 0x55)

    def test_response_get_special_memory_range_location(self):
        self.proto.set_address_size_bits(32)
        response = self.proto.respond_special_memory_region_location(cmd.GetInfo.MemoryRangeType.Forbidden, 0x12, start=0x11223344, end=0x99887766)
        self.assert_req_response_bytes(response, [0x81, 5, 0, 0, 10, 1, 0x12, 0x11, 0x22, 0x33, 0x44, 0x99, 0x88, 0x77, 0x66])
        data = self.proto.parse_response(response)
        self.assertEqual(data['region_type'], cmd.GetInfo.MemoryRangeType.Forbidden)
        self.assertEqual(data['region_index'], 0x12)
        self.assertEqual(data['start'], 0x11223344)
        self.assertEqual(data['end'], 0x99887766)
    
    def test_response_get_rpv_count(self):
        response = self.proto.respond_get_rpv_count(0x1234)
        self.assert_req_response_bytes(response, [0x81, 6, 0, 0, 2, 0x12, 0x34])
        data = self.proto.parse_response(response)
        self.assertEqual(data['count'], 0x1234)

    def test_response_get_rpv_definition(self):
        definitions = [
            dict(id=0x1234, type=VariableType.float32, read=True, write=False),
            dict(id=0x9875, type=VariableType.uint32, read=True, write=True)
        ]

        definition_payloads = [
            [0x12, 0x34, VariableType.float32.value, 0x01],
            [0x98, 0x75, VariableType.uint32.value, 0x03]
        ]

        response = self.proto.respond_get_rpv_definition(definitions)
        self.assert_req_response_bytes(response, [0x81, 7, 0, 0, 8] + definition_payloads[0] + definition_payloads[1])
        data = self.proto.parse_response(response)
        self.assertEqual(len(data['rpvs']), 2)
        self.assertEqual(data['rpvs'][0]['id'], 0x1234)
        self.assertEqual(data['rpvs'][0]['type'], VariableType.float32)
        self.assertEqual(data['rpvs'][0]['read'], True)
        self.assertEqual(data['rpvs'][0]['write'], False)
        self.assertEqual(data['rpvs'][1]['id'], 0x9875)
        self.assertEqual(data['rpvs'][1]['type'], VariableType.uint32)
        self.assertEqual(data['rpvs'][1]['read'], True)
        self.assertEqual(data['rpvs'][1]['write'], True)


# ============= MemoryControl ===============

    def test_response_read_single_memory_block_8bits(self):
        self.proto.set_address_size_bits(8)
        response = self.proto.respond_read_single_memory_block(0x99, bytes([0x11, 0x22, 0x33]))
        self.assert_req_response_bytes(response, [0x83, 1, 0, 0, 6, 0x99, 0x00, 0x03, 0x11, 0x22, 0x33])
        data = self.proto.parse_response(response)
        self.assertEqual(data['read_blocks'][0]['address'], 0x99)
        self.assertEqual(data['read_blocks'][0]['data'], bytes([0x11, 0x22, 0x33]))

    def test_response_read_multiple_memory_block_8bits(self):
        self.proto.set_address_size_bits(8)
        blocks = []
        blocks.append((0x99, bytes([0x11, 0x22, 0x33])))
        blocks.append((0x88, bytes([0xFF, 0xEE, 0xDD])))
        response = self.proto.respond_read_memory_blocks(blocks)
        self.assert_req_response_bytes(response, [0x83, 1, 0, 0, 12, 0x99, 0x00, 0x03, 0x11, 0x22, 0x33, 0x88, 0x00, 0x03, 0xFF, 0xEE, 0xDD])
        data = self.proto.parse_response(response)
        self.assertEqual(data['read_blocks'][0]['address'], 0x99)
        self.assertEqual(data['read_blocks'][0]['data'], bytes([0x11, 0x22, 0x33]))
        self.assertEqual(data['read_blocks'][1]['address'], 0x88)
        self.assertEqual(data['read_blocks'][1]['data'], bytes([0xFF, 0xEE, 0xDD]))

    def test_response_read_single_memory_block_16bits(self):
        self.proto.set_address_size_bits(16)
        response = self.proto.respond_read_single_memory_block(0x8899, bytes([0x11, 0x22, 0x33]))
        self.assert_req_response_bytes(response, [0x83, 1, 0, 0, 7, 0x88, 0x99, 0x00, 0x03, 0x11, 0x22, 0x33])
        data = self.proto.parse_response(response)
        self.assertEqual(data['read_blocks'][0]['address'], 0x8899)
        self.assertEqual(data['read_blocks'][0]['data'], bytes([0x11, 0x22, 0x33]))

    def test_response_read_multiple_memory_block_16bits(self):
        self.proto.set_address_size_bits(16)
        blocks = []
        blocks.append((0x6789, bytes([0x11, 0x22, 0x33])))
        blocks.append((0x9876, bytes([0xFF, 0xEE, 0xDD])))
        response = self.proto.respond_read_memory_blocks(blocks)
        self.assert_req_response_bytes(response, [0x83, 1, 0, 0, 14, 0x67, 0x89, 0x00, 0x03, 0x11,
                                       0x22, 0x33, 0x98, 0x76, 0x00, 0x03, 0xFF, 0xEE, 0xDD])
        data = self.proto.parse_response(response)
        self.assertEqual(data['read_blocks'][0]['address'], 0x6789)
        self.assertEqual(data['read_blocks'][0]['data'], bytes([0x11, 0x22, 0x33]))
        self.assertEqual(data['read_blocks'][1]['address'], 0x9876)
        self.assertEqual(data['read_blocks'][1]['data'], bytes([0xFF, 0xEE, 0xDD]))

    def test_response_read_single_memory_block_32bits(self):
        self.proto.set_address_size_bits(32)
        response = self.proto.respond_read_single_memory_block(0x12345678, bytes([0x11, 0x22, 0x33]))
        self.assert_req_response_bytes(response, [0x83, 1, 0, 0, 9, 0x12, 0x34, 0x56, 0x78, 0x00, 0x03, 0x11, 0x22, 0x33])
        data = self.proto.parse_response(response)
        self.assertEqual(data['read_blocks'][0]['address'], 0x12345678)
        self.assertEqual(data['read_blocks'][0]['data'], bytes([0x11, 0x22, 0x33]))

    def test_response_read_multiple_memory_block_32bits(self):
        self.proto.set_address_size_bits(32)
        blocks = []
        blocks.append((0x12345678, bytes([0x11, 0x22, 0x33])))
        blocks.append((0x11223344, bytes([0xFF, 0xEE, 0xDD])))
        response = self.proto.respond_read_memory_blocks(blocks)
        self.assert_req_response_bytes(response, [0x83, 1, 0, 0, 18, 0x12, 0x34, 0x56, 0x78, 0x00, 0x03,
                                       0x11, 0x22, 0x33, 0x11, 0x22, 0x33, 0x44, 0x00, 0x03, 0xFF, 0xEE, 0xDD])
        data = self.proto.parse_response(response)
        self.assertEqual(data['read_blocks'][0]['address'], 0x12345678)
        self.assertEqual(data['read_blocks'][0]['data'], bytes([0x11, 0x22, 0x33]))
        self.assertEqual(data['read_blocks'][1]['address'], 0x11223344)
        self.assertEqual(data['read_blocks'][1]['data'], bytes([0xFF, 0xEE, 0xDD]))

    def test_response_read_single_memory_block_64bits(self):
        self.proto.set_address_size_bits(64)
        response = self.proto.respond_read_single_memory_block(0x123456789abcdef0, bytes([0x11, 0x22, 0x33]))
        self.assert_req_response_bytes(response, [0x83, 1, 0, 0, 13, 0x12, 0x34, 0x56, 0x78, 0x9a, 0xbc, 0xde, 0xf0, 0x00, 0x03, 0x11, 0x22, 0x33])
        data = self.proto.parse_response(response)
        self.assertEqual(data['read_blocks'][0]['address'], 0x123456789abcdef0)
        self.assertEqual(data['read_blocks'][0]['data'], bytes([0x11, 0x22, 0x33]))

    def test_response_read_multiple_memory_block_64bits(self):
        self.proto.set_address_size_bits(64)
        blocks = []
        blocks.append((0xFEDCBA9876543210, bytes([0x11, 0x22, 0x33])))
        blocks.append((0x123456789abcdef0, bytes([0xFF, 0xEE, 0xDD])))
        response = self.proto.respond_read_memory_blocks(blocks)
        self.assert_req_response_bytes(response, [0x83, 1, 0, 0, 26, 0xFE, 0xDC, 0xBA, 0x98, 0x76, 0x54, 0x32, 0x10,
                                       0x00, 0x03, 0x11, 0x22, 0x33, 0x12, 0x34, 0x56, 0x78, 0x9a, 0xbc, 0xde, 0xf0, 0x00, 0x03, 0xFF, 0xEE, 0xDD])
        data = self.proto.parse_response(response)
        self.assertEqual(data['read_blocks'][0]['address'], 0xFEDCBA9876543210)
        self.assertEqual(data['read_blocks'][0]['data'], bytes([0x11, 0x22, 0x33]))
        self.assertEqual(data['read_blocks'][1]['address'], 0x123456789abcdef0)
        self.assertEqual(data['read_blocks'][1]['data'], bytes([0xFF, 0xEE, 0xDD]))

    def test_parse_response_read_memory_block_invalid_content(self):
        self.proto.logger.disabled = True
        response = Response(cmd.MemoryControl, cmd.MemoryControl.Subfunction.Read, Response.ResponseCode.OK)
        with self.assertRaises(Exception):
            response.data = bytes([0x12, 0x34, 0x56, 0x78, 0x00, 0x03, 0x11, 0x22])
            self.proto.parse_response(response)

        with self.assertRaises(Exception):
            response.data = bytes([0x12, 0x34, 0x56, 0x78, 0x00, 0x03, 0x11, 0x22, 0x33, 0x44])
            self.proto.parse_response(response)

    def test_response_write_single_memory_block_8bits(self):
        self.proto.set_address_size_bits(8)
        response = self.proto.respond_write_single_memory_block(0x12, 0x1122)
        self.assert_req_response_bytes(response, [0x83, 2, 0, 0, 3, 0x12, 0x11, 0x22])
        data = self.proto.parse_response(response)
        self.assertEqual(data['written_blocks'][0]['address'], 0x12)
        self.assertEqual(data['written_blocks'][0]['length'], 0x1122)

    def test_response_write_single_memory_block_8bits_masked(self):
        self.proto.set_address_size_bits(8)
        response = self.proto.respond_write_single_memory_block_masked(0x12, 0x1122)
        self.assert_req_response_bytes(response, [0x83, 3, 0, 0, 3, 0x12, 0x11, 0x22])
        data = self.proto.parse_response(response)
        self.assertEqual(data['written_blocks'][0]['address'], 0x12)
        self.assertEqual(data['written_blocks'][0]['length'], 0x1122)

    def test_response_write_multiple_memory_block_8bits(self):
        self.proto.set_address_size_bits(8)
        blocks = []
        blocks.append((0x12, 0x1122))
        blocks.append((0x21, 0x3344))
        response = self.proto.respond_write_memory_blocks(blocks)
        self.assert_req_response_bytes(response, [0x83, 2, 0, 0, 6, 0x12, 0x11, 0x22, 0x21, 0x33, 0x44])
        data = self.proto.parse_response(response)
        self.assertEqual(data['written_blocks'][0]['address'], 0x12)
        self.assertEqual(data['written_blocks'][0]['length'], 0x1122)
        self.assertEqual(data['written_blocks'][1]['address'], 0x21)
        self.assertEqual(data['written_blocks'][1]['length'], 0x3344)

    def test_response_write_multiple_memory_block_8bits_masked(self):
        self.proto.set_address_size_bits(8)
        blocks = []
        blocks.append((0x12, 0x1122))
        blocks.append((0x21, 0x3344))
        response = self.proto.respond_write_memory_blocks_masked(blocks)
        self.assert_req_response_bytes(response, [0x83, 3, 0, 0, 6, 0x12, 0x11, 0x22, 0x21, 0x33, 0x44])
        data = self.proto.parse_response(response)
        self.assertEqual(data['written_blocks'][0]['address'], 0x12)
        self.assertEqual(data['written_blocks'][0]['length'], 0x1122)
        self.assertEqual(data['written_blocks'][1]['address'], 0x21)
        self.assertEqual(data['written_blocks'][1]['length'], 0x3344)

    def test_response_write_single_memory_block_16bits(self):
        self.proto.set_address_size_bits(16)
        response = self.proto.respond_write_single_memory_block(0x1234, 0x1122)
        self.assert_req_response_bytes(response, [0x83, 2, 0, 0, 4, 0x12, 0x34, 0x11, 0x22])
        data = self.proto.parse_response(response)
        self.assertEqual(data['written_blocks'][0]['address'], 0x1234)
        self.assertEqual(data['written_blocks'][0]['length'], 0x1122)

    def test_response_write_single_memory_block_16bits_masked(self):
        self.proto.set_address_size_bits(16)
        response = self.proto.respond_write_single_memory_block_masked(0x1234, 0x1122)
        self.assert_req_response_bytes(response, [0x83, 3, 0, 0, 4, 0x12, 0x34, 0x11, 0x22])
        data = self.proto.parse_response(response)
        self.assertEqual(data['written_blocks'][0]['address'], 0x1234)
        self.assertEqual(data['written_blocks'][0]['length'], 0x1122)

    def test_response_write_multiple_memory_block_16bits(self):
        self.proto.set_address_size_bits(16)
        blocks = []
        blocks.append((0x1234, 0x1122))
        blocks.append((0x4321, 0x3344))
        response = self.proto.respond_write_memory_blocks(blocks)
        self.assert_req_response_bytes(response, [0x83, 2, 0, 0, 8, 0x12, 0x34, 0x11, 0x22, 0x43, 0x21, 0x33, 0x44])
        data = self.proto.parse_response(response)
        self.assertEqual(data['written_blocks'][0]['address'], 0x1234)
        self.assertEqual(data['written_blocks'][0]['length'], 0x1122)
        self.assertEqual(data['written_blocks'][1]['address'], 0x4321)
        self.assertEqual(data['written_blocks'][1]['length'], 0x3344)

    def test_response_write_multiple_memory_block_16bits_masked(self):
        self.proto.set_address_size_bits(16)
        blocks = []
        blocks.append((0x1234, 0x1122))
        blocks.append((0x4321, 0x3344))
        response = self.proto.respond_write_memory_blocks_masked(blocks)
        self.assert_req_response_bytes(response, [0x83, 3, 0, 0, 8, 0x12, 0x34, 0x11, 0x22, 0x43, 0x21, 0x33, 0x44])
        data = self.proto.parse_response(response)
        self.assertEqual(data['written_blocks'][0]['address'], 0x1234)
        self.assertEqual(data['written_blocks'][0]['length'], 0x1122)
        self.assertEqual(data['written_blocks'][1]['address'], 0x4321)
        self.assertEqual(data['written_blocks'][1]['length'], 0x3344)

    def test_response_write_single_memory_block_32bits(self):
        self.proto.set_address_size_bits(32)
        response = self.proto.respond_write_single_memory_block(0x12345678, 0x1122)
        self.assert_req_response_bytes(response, [0x83, 2, 0, 0, 6, 0x12, 0x34, 0x56, 0x78, 0x11, 0x22])
        data = self.proto.parse_response(response)
        self.assertEqual(data['written_blocks'][0]['address'], 0x12345678)
        self.assertEqual(data['written_blocks'][0]['length'], 0x1122)

    def test_response_write_single_memory_block_32bits_masked(self):
        self.proto.set_address_size_bits(32)
        response = self.proto.respond_write_single_memory_block_masked(0x12345678, 0x1122)
        self.assert_req_response_bytes(response, [0x83, 3, 0, 0, 6, 0x12, 0x34, 0x56, 0x78, 0x11, 0x22])
        data = self.proto.parse_response(response)
        self.assertEqual(data['written_blocks'][0]['address'], 0x12345678)
        self.assertEqual(data['written_blocks'][0]['length'], 0x1122)

    def test_response_write_multiple_memory_block_32bits(self):
        self.proto.set_address_size_bits(32)
        blocks = []
        blocks.append((0x12345678, 0x1122))
        blocks.append((0x87654321, 0x3344))
        response = self.proto.respond_write_memory_blocks(blocks)
        self.assert_req_response_bytes(response, [0x83, 2, 0, 0, 12, 0x12, 0x34, 0x56, 0x78, 0x11, 0x22, 0x87, 0x65, 0x43, 0x21, 0x33, 0x44])
        data = self.proto.parse_response(response)
        self.assertEqual(data['written_blocks'][0]['address'], 0x12345678)
        self.assertEqual(data['written_blocks'][0]['length'], 0x1122)
        self.assertEqual(data['written_blocks'][1]['address'], 0x87654321)
        self.assertEqual(data['written_blocks'][1]['length'], 0x3344)

    def test_response_write_multiple_memory_block_32bits_masked(self):
        self.proto.set_address_size_bits(32)
        blocks = []
        blocks.append((0x12345678, 0x1122))
        blocks.append((0x87654321, 0x3344))
        response = self.proto.respond_write_memory_blocks_masked(blocks)
        self.assert_req_response_bytes(response, [0x83, 3, 0, 0, 12, 0x12, 0x34, 0x56, 0x78, 0x11, 0x22, 0x87, 0x65, 0x43, 0x21, 0x33, 0x44])
        data = self.proto.parse_response(response)
        self.assertEqual(data['written_blocks'][0]['address'], 0x12345678)
        self.assertEqual(data['written_blocks'][0]['length'], 0x1122)
        self.assertEqual(data['written_blocks'][1]['address'], 0x87654321)
        self.assertEqual(data['written_blocks'][1]['length'], 0x3344)

    def test_response_write_single_memory_block_64bits(self):
        self.proto.set_address_size_bits(64)
        response = self.proto.respond_write_single_memory_block(0x123456789abcdef0, 0x1122)
        self.assert_req_response_bytes(response, [0x83, 2, 0, 0, 10, 0x12, 0x34, 0x56, 0x78, 0x9a, 0xbc, 0xde, 0xf0, 0x11, 0x22])
        data = self.proto.parse_response(response)
        self.assertEqual(data['written_blocks'][0]['address'], 0x123456789abcdef0)
        self.assertEqual(data['written_blocks'][0]['length'], 0x1122)

    def test_response_write_single_memory_block_64bits_masked(self):
        self.proto.set_address_size_bits(64)
        response = self.proto.respond_write_single_memory_block_masked(0x123456789abcdef0, 0x1122)
        self.assert_req_response_bytes(response, [0x83, 3, 0, 0, 10, 0x12, 0x34, 0x56, 0x78, 0x9a, 0xbc, 0xde, 0xf0, 0x11, 0x22])
        data = self.proto.parse_response(response)
        self.assertEqual(data['written_blocks'][0]['address'], 0x123456789abcdef0)
        self.assertEqual(data['written_blocks'][0]['length'], 0x1122)

    def test_response_write_multiple_memory_block_64bits(self):
        self.proto.set_address_size_bits(64)
        blocks = []
        blocks.append((0x123456789abcdef0, 0x1122))
        blocks.append((0xfedcba9876543210, 0x3344))
        response = self.proto.respond_write_memory_blocks(blocks)
        self.assert_req_response_bytes(response, [0x83, 2, 0, 0, 20, 0x12, 0x34, 0x56, 0x78, 0x9a, 0xbc, 0xde,
                                       0xf0, 0x11, 0x22, 0xfe, 0xdc, 0xba, 0x98, 0x76, 0x54, 0x32, 0x10, 0x33, 0x44])
        data = self.proto.parse_response(response)
        self.assertEqual(data['written_blocks'][0]['address'], 0x123456789abcdef0)
        self.assertEqual(data['written_blocks'][0]['length'], 0x1122)
        self.assertEqual(data['written_blocks'][1]['address'], 0xfedcba9876543210)
        self.assertEqual(data['written_blocks'][1]['length'], 0x3344)

    def test_response_write_multiple_memory_block_64bits_masked(self):
        self.proto.set_address_size_bits(64)
        blocks = []
        blocks.append((0x123456789abcdef0, 0x1122))
        blocks.append((0xfedcba9876543210, 0x3344))
        response = self.proto.respond_write_memory_blocks_masked(blocks)
        self.assert_req_response_bytes(response, [0x83, 3, 0, 0, 20, 0x12, 0x34, 0x56, 0x78, 0x9a, 0xbc, 0xde,
                                       0xf0, 0x11, 0x22, 0xfe, 0xdc, 0xba, 0x98, 0x76, 0x54, 0x32, 0x10, 0x33, 0x44])
        data = self.proto.parse_response(response)
        self.assertEqual(data['written_blocks'][0]['address'], 0x123456789abcdef0)
        self.assertEqual(data['written_blocks'][0]['length'], 0x1122)
        self.assertEqual(data['written_blocks'][1]['address'], 0xfedcba9876543210)
        self.assertEqual(data['written_blocks'][1]['length'], 0x3344)

    def test_response_write_single_memory_block_32bits_bad_response(self):
        self.proto.set_address_size_bits(32)
        response = Response(cmd.MemoryControl, cmd.MemoryControl.Subfunction.Write, Response.ResponseCode.OK, [0x12, 0x34, 0x56, 0x78, 0x11])
        with self.assertRaises(Exception):
            data = self.proto.parse_response(response)

        response = Response(cmd.MemoryControl, cmd.MemoryControl.Subfunction.Write,
                            Response.ResponseCode.OK, [0x12, 0x34, 0x56, 0x78, 0x11, 0x22, 0x33])
        with self.assertRaises(Exception):
            data = self.proto.parse_response(response)

# ============= CommControl ===============

    def test_response_comm_discover(self):
        firmwareid = bytes(range(16))
        display_name = 'hello'
        payload_length = 1 + 1 + len(firmwareid) + 1 + len(display_name.encode('utf8'))
        payload_data = bytes([self.proto.version_major, self.proto.version_minor]) + firmwareid + \
            struct.pack('B', len(display_name)) + display_name.encode('utf8')
        response_bytes = bytes([0x82, 1, 0, 0, payload_length]) + payload_data
        response = self.proto.respond_comm_discover(firmwareid, display_name)
        self.assert_req_response_bytes(response, response_bytes)
        data = self.proto.parse_response(response)
        self.assertEqual(data['protocol_major'], self.proto.version_major)
        self.assertEqual(data['protocol_minor'], self.proto.version_minor)
        self.assertEqual(data['firmware_id'], firmwareid)
        self.assertEqual(data['display_name'], display_name)

    def test_response_comm_heartbeat(self):
        response = self.proto.respond_comm_heartbeat(session_id=0x12345678, challenge_response=0x1122)
        self.assert_req_response_bytes(response, [0x82, 2, 0, 0, 6, 0x12, 0x34, 0x56, 0x78, 0x11, 0x22])
        data = self.proto.parse_response(response)
        self.assertEqual(data['session_id'], 0x12345678)
        self.assertEqual(data['challenge_response'], 0x1122)

    def test_response_comm_get_params(self):
        response = self.proto.respond_comm_get_params(max_rx_data_size=0x1234, max_tx_data_size=0x4321,
                                                      max_bitrate_bps=0x11223344, heartbeat_timeout_us=0x99887766, rx_timeout_us=0x98765432, address_size_byte=4);
        self.assert_req_response_bytes(response, [0x82, 3, 0, 0, 17, 0x12, 0x34, 0x43, 0x21, 0x11, 0x22,
                                       0x33, 0x44, 0x99, 0x88, 0x77, 0x66, 0x98, 0x76, 0x54, 0x32, 0x04]);
        data = self.proto.parse_response(response)
        self.assertEqual(data['max_rx_data_size'], 0x1234)
        self.assertEqual(data['max_tx_data_size'], 0x4321)
        self.assertEqual(data['max_bitrate_bps'], 0x11223344)
        self.assertEqual(data['heartbeat_timeout_us'], 0x99887766)
        self.assertEqual(data['rx_timeout_us'], 0x98765432)
        self.assertEqual(data['address_size_byte'], 4)

    def test_response_comm_connect(self):
        magic = bytes([0x82, 0x90, 0x22, 0x66])
        response_data = bytes([0x82, 4, 0, 0, 8]) + magic + bytes([0x12, 0x34, 0x56, 0x78])
        response = self.proto.respond_comm_connect(0x12345678)
        self.assert_req_response_bytes(response, response_data)
        data = self.proto.parse_response(response)
        self.assertEqual(data['session_id'], 0x12345678)

    def test_response_comm_disconnect(self):
        response = self.proto.respond_comm_disconnect()
        self.assert_req_response_bytes(response, [0x82, 5, 0, 0, 0])
        data = self.proto.parse_response(response)

# ============= Datalog ===============

    def test_response_datalog_get_targets(self):
        targets = []
        targets.append(DatalogLocation(target_id=0, location_type=DatalogLocation.LocationType.RAM, name='RAM'))
        targets.append(DatalogLocation(target_id=2, location_type=DatalogLocation.LocationType.ROM, name='FLASH'))
        targets.append(DatalogLocation(target_id=5, location_type=DatalogLocation.LocationType.EXTERNAL, name='SD CARD'))

        payload = bytes([0, 0, 3]) + 'RAM'.encode('ASCII')
        payload += bytes([2, 1, 5]) + 'FLASH'.encode('ASCII')
        payload += bytes([5, 2, 7]) + 'SD CARD'.encode('ASCII')

        payload = bytes([0x85, 1, 0]) + struct.pack('>H', len(payload)) + payload
        response = self.proto.respond_data_get_targets(targets)

        self.assert_req_response_bytes(response, payload)
        data = self.proto.parse_response(response)
        targets = data['targets']
        self.assertEqual(len(targets), 3)

        self.assertEqual(targets[0].target_id, 0)
        self.assertEqual(targets[0].name, 'RAM')
        self.assertEqual(targets[0].location_type, DatalogLocation.LocationType.RAM)

        self.assertEqual(targets[1].target_id, 2)
        self.assertEqual(targets[1].name, 'FLASH')
        self.assertEqual(targets[1].location_type, DatalogLocation.LocationType.ROM)

        self.assertEqual(targets[2].target_id, 5)
        self.assertEqual(targets[2].name, 'SD CARD')
        self.assertEqual(targets[2].location_type, DatalogLocation.LocationType.EXTERNAL)

    def test_response_datalog_get_buffer_size(self):
        response = self.proto.respond_datalog_get_bufsize(0x12345678)
        self.assert_req_response_bytes(response, [0x85, 2, 0, 0, 4, 0x12, 0x34, 0x56, 0x78])
        data = self.proto.parse_response(response)
        self.assertEqual(data['size'], 0x12345678)

    def test_response_datalog_get_sampling_rates(self):
        response = self.proto.respond_datalog_get_sampling_rates([0.1, 1, 10])
        payload = bytes([0x85, 3, 0, 0, 12]) + struct.pack('>fff', 0.1, 1, 10)
        self.assert_req_response_bytes(response, payload)
        data = self.proto.parse_response(response)
        self.assertEqual(len(data['sampling_rates']), 3)
        self.assertAlmostEqual(data['sampling_rates'][0], 0.1, 5)
        self.assertAlmostEqual(data['sampling_rates'][1], 1, 5)
        self.assertAlmostEqual(data['sampling_rates'][2], 10, 5)

    def test_response_datalog_arm_log(self):
        response = self.proto.respond_datalog_arm(record_id=0x1234)
        self.assert_req_response_bytes(response, [0x85, 7, 0, 0, 2, 0x12, 0x34])
        data = self.proto.parse_response(response)
        self.assertEqual(data['record_id'], 0x1234)

    def test_response_datalog_disarm_log(self):
        response = self.proto.respond_datalog_disarm()
        self.assert_req_response_bytes(response, [0x85, 8, 0, 0, 0])
        data = self.proto.parse_response(response)

    def test_response_datalog_get_log_status(self):
        response = self.proto.respond_datalog_status(status=LogStatus.Triggered)
        self.assert_req_response_bytes(response, [0x85, 9, 0, 0, 1, 1])
        data = self.proto.parse_response(response)
        self.assertEqual(data['status'], LogStatus.Triggered)

    def test_response_datalog_list_records(self):
        recordings = []
        recordings.append(RecordInfo(record_id=0x1234, location_type=DatalogLocation.LocationType.RAM, size=0x201))
        recordings.append(RecordInfo(record_id=0x4567, location_type=DatalogLocation.LocationType.ROM, size=0x333))
        response = self.proto.respond_datalog_list_recordings(recordings)
        self.assert_req_response_bytes(response, [0x85, 5, 0, 0, 10, 0x12, 0x34, 0, 0x02, 0x01, 0x45, 0x67, 1, 0x03, 0x33])
        data = self.proto.parse_response(response)
        self.assertEqual(len(data['recordings']), 2)
        self.assertEqual(data['recordings'][0].record_id, 0x1234)
        self.assertEqual(data['recordings'][0].location_type, DatalogLocation.LocationType.RAM)
        self.assertEqual(data['recordings'][0].size, 0x201)
        self.assertEqual(data['recordings'][1].record_id, 0x4567)
        self.assertEqual(data['recordings'][1].location_type, DatalogLocation.LocationType.ROM)
        self.assertEqual(data['recordings'][1].size, 0x333)

    def test_response_datalog_read_recording(self):
        record_data = bytes(range(256))
        response = self.proto.respond_read_recording(record_id=0x1234, data=record_data)
        payload = bytes([0x85, 6, 0, 1, 2, 0x12, 0x34]) + record_data
        self.assert_req_response_bytes(response, payload)
        data = self.proto.parse_response(response)
        self.assertEqual(data['record_id'], 0x1234)
        self.assertEqual(data['data'], record_data)

    def test_response_datalog_configure_log(self):
        record_data = bytes(range(256))
        response = self.proto.respond_configure_log(record_id=0x1234)
        payload = bytes([0x85, 4, 0, 0, 2, 0x12, 0x34])
        self.assert_req_response_bytes(response, payload)
        data = self.proto.parse_response(response)
        self.assertEqual(data['record_id'], 0x1234)

# ============= UserCommand ===============

    def test_response_user_cmd(self):
        response = self.proto.respond_user_command(10, bytes([1, 2, 3]))
        self.assert_req_response_bytes(response, [0x84, 10, 0, 0, 3, 1, 2, 3])
        self.assertEqual(response.subfn, 10)
        self.assertEqual(response.payload, bytes([1, 2, 3]))

if __name__ == '__main__':
    unittest.main()