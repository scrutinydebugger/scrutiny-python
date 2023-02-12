#    test_protocol_v1_0.py
#        Test the Scrutiny Protocol.
#         Validate encoding and decoding of each command.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import struct
from scrutiny.server.protocol import Protocol, Request, Response
from scrutiny.server.protocol import commands as cmd
from scrutiny.core.basic_types import EmbeddedDataType, RuntimePublishedValue
import scrutiny.server.protocol.typing as protocol_typing
import scrutiny.server.datalogging.definitions.device as device_datalogging
from test import ScrutinyUnitTest
from scrutiny.server.device.device_info import *

from scrutiny.server.protocol.crc32 import crc32
from typing import List, cast


def d2f(d):
    return struct.unpack('f', struct.pack('f', d))[0]


class TestProtocolV1_0(ScrutinyUnitTest):

    def setUp(self):
        self.proto = Protocol(1, 0, address_size_bits=32)
        self.proto.logger.disabled = False

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

    def assert_address_encode(self, nbits: int, address: int, vals: List[int]):
        self.proto.set_address_size_bits(nbits)
        buff = self.proto.encode_address(address)
        vals2 = list(map(lambda x: int(x), buff))
        self.assertEqual(len(buff), len(vals))
        self.assertEqual(vals, vals2)

    def test_address_encoding(self):
        self.assert_address_encode(8, 5, [5])
        self.assert_address_encode(8, 256, [0])
        self.assert_address_encode(8, 257, [1])
        self.assert_address_encode(8, 513, [1])
        self.assert_address_encode(8, -1, [255])

        self.assert_address_encode(16, 0x1234, [0x12, 0x34])
        self.assert_address_encode(16, 0xFFFF, [0xFF, 0xFF])
        self.assert_address_encode(16, 0x10000, [0, 0])
        self.assert_address_encode(16, 0x10001, [0, 1])
        self.assert_address_encode(16, 0x100001, [0, 1])
        self.assert_address_encode(16, -1, [0xFF, 0xFF])

        self.assert_address_encode(32, 0x12345678, [0x12, 0x34, 0x56, 0x78])
        self.assert_address_encode(32, 0x100000000, [0, 0, 0, 0])
        self.assert_address_encode(32, 0x1000000001, [0, 0, 0, 1])
        self.assert_address_encode(32, -1, [0xFF, 0xFF, 0xFF, 0xFF])

        self.assert_address_encode(64, 0x123456789abcdef0, [0x12, 0x34, 0x56, 0x78, 0x9a, 0xbc, 0xde, 0xf0])
        self.assert_address_encode(64, 0x10000000000000000, [0, 0, 0, 0, 0, 0, 0, 0])
        self.assert_address_encode(64, 0x10000000000000001, [0, 0, 0, 0, 0, 0, 0, 1])
        self.assert_address_encode(64, -1, [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])


# ============================
#               Request
# ============================

# region Request GetInfo


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
        self.check_expected_payload_size(req, (2 + 1) * 5)    # id, type

    def test_req_get_loop_count(self):
        req = self.proto.get_loop_count()
        self.assert_req_response_bytes(req, [1, 8, 0, 0])
        data = self.proto.parse_request(req)
        self.check_expected_payload_size(req, 1)

    def test_req_get_loop_definition(self):
        req = self.proto.get_loop_definition(loop_id=0xa5)
        self.assert_req_response_bytes(req, [1, 9, 0, 1, 0xa5])
        data = self.proto.parse_request(req)
        self.check_expected_payload_size(req, 1 + 1 + 4 + 1 + 32)    # Maximum size
        self.assertEqual(data['loop_id'], 0xa5)


# endregion

# region Request MemoryControl

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

    def test_req_read_single_rpv(self):
        self.proto.configure_rpvs([
            RuntimePublishedValue(id=0x1234, datatype=EmbeddedDataType.uint32),
            RuntimePublishedValue(id=0x5678, datatype=EmbeddedDataType.uint16)
        ])

        req = self.proto.read_runtime_published_values(0x1234)
        self.assert_req_response_bytes(req, [3, 4, 0, 2, 0x12, 0x34])
        data = self.proto.parse_request(req)
        self.assertEqual(data['rpvs_id'][0], 0x1234)
        self.check_expected_payload_size(req, 2 + 4)

    def test_req_read_multiple_rpv(self):
        self.proto.configure_rpvs([
            RuntimePublishedValue(id=0x1234, datatype=EmbeddedDataType.uint32),
            RuntimePublishedValue(id=0x5678, datatype=EmbeddedDataType.uint16)
        ])

        req = self.proto.read_runtime_published_values([0x1234, 0x5678])
        self.assert_req_response_bytes(req, [3, 4, 0, 4, 0x12, 0x34, 0x56, 0x78])
        data = self.proto.parse_request(req)
        self.assertEqual(data['rpvs_id'][0], 0x1234)
        self.assertEqual(data['rpvs_id'][1], 0x5678)
        self.check_expected_payload_size(req, 2 + 4 + 2 + 2)

    def test_req_read_rpv_not_in_config(self):
        self.proto.configure_rpvs([
            RuntimePublishedValue(id=0x1234, datatype=EmbeddedDataType.uint32),
            RuntimePublishedValue(id=0x5678, datatype=EmbeddedDataType.uint16)
        ])

        with self.assertRaises(Exception):
            self.proto.read_runtime_published_values([0x1234, 0x5678, 0x9999])

    def test_write_single_rpv(self):
        config = [
            RuntimePublishedValue(id=0x1234, datatype=EmbeddedDataType.uint32)
        ]
        self.proto.configure_rpvs(config)

        req = self.proto.write_runtime_published_values((0x1234, 0x11223344))

        self.assert_req_response_bytes(req, [3, 5, 0, 6, 0x12, 0x34, 0x11, 0x22, 0x33, 0x44])
        data = self.proto.parse_request(req)
        self.assertEqual(data['rpvs'][0]['id'], 0x1234)
        self.assertEqual(data['rpvs'][0]['value'], 0x11223344)
        self.check_expected_payload_size(req, 3)    # ID + size

    def test_write_multiple_rpvs(self):
        config = [
            RuntimePublishedValue(id=0x1234, datatype=EmbeddedDataType.uint32),
            RuntimePublishedValue(id=0x5678, datatype=EmbeddedDataType.uint16)
        ]
        self.proto.configure_rpvs(config)

        req = self.proto.write_runtime_published_values([(0x1234, 0x11223344), (0x5678, 0x8899)])

        self.assert_req_response_bytes(req, [3, 5, 0, 10, 0x12, 0x34, 0x11, 0x22, 0x33, 0x44, 0x56, 0x78, 0x88, 0x99])
        data = self.proto.parse_request(req)
        self.assertEqual(data['rpvs'][0]['id'], 0x1234)
        self.assertEqual(data['rpvs'][0]['value'], 0x11223344)
        self.assertEqual(data['rpvs'][1]['id'], 0x5678)
        self.assertEqual(data['rpvs'][1]['value'], 0x8899)

        self.check_expected_payload_size(req, 6)    # 2x ID + size

    def test_write_rpv_not_in_config(self):
        config = [
            RuntimePublishedValue(id=0x1234, datatype=EmbeddedDataType.uint32)
        ]
        self.proto.configure_rpvs(config)

        with self.assertRaises(Exception):
            self.proto.write_runtime_published_values((0x1235, 0x11223344))

    def test_write_rpv_bad_type(self):
        config = [
            RuntimePublishedValue(id=0x1234, datatype=EmbeddedDataType.uint32)
        ]
        self.proto.configure_rpvs(config)

        with self.assertRaises(Exception):
            self.proto.write_runtime_published_values((0x1234, 1.345))
# endregion

# region Request CommControl
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
# endregion

# region Request Datalogging

    def test_req_datalogging_get_setup(self):
        request_bytes = bytes([5, 1, 0, 0])
        req = self.proto.datalogging_get_setup()
        self.assert_req_response_bytes(req, request_bytes)
        data = self.proto.parse_request(req)
        self.check_expected_payload_size(req, 6)

    def test_req_datalogging_configure(self):
        self.proto.set_address_size_bits(32)

        config = device_datalogging.Configuration()
        config.decimation = 0x1234
        config.probe_location = 0.5
        config.timeout = 2.5              # 2.5sec
        config.trigger_hold_time = 0.001  # 1msec
        config.trigger_condition = device_datalogging.TriggerCondition(
            device_datalogging.TriggerConditionID.IsWithin,
            device_datalogging.RPVOperand(0x1234),
            device_datalogging.VarBitOperand(address=0x99887766, datatype=EmbeddedDataType.uint32, bitoffset=5, bitsize=12),
            device_datalogging.LiteralOperand(1)
        )
        config.add_signal(device_datalogging.MemoryLoggableSignal(0x55443322, 4))
        config.add_signal(device_datalogging.TimeLoggableSignal())
        config.add_signal(device_datalogging.RPVLoggableSignal(0xabcd))

        req = self.proto.datalogging_configure(loop_id=1, config_id=0xaabb, config=config)
        request_bytes = bytes([5, 2, 0, 43, 1, 0xaa, 0xbb, 0x12, 0x34, 128])   # cmd, subfn, loop_id, config_id, decimation, probe_location
        request_bytes += struct.pack('>L', 25000000) + bytes([8]) + struct.pack('>L', 10000) + \
            bytes([3])    # timeout, condition_id, hold_time, nb_operand
        request_bytes += bytes([3, 0x12, 0x34])  # Operand 1    - OperandType(1), RpvId(2)
        # Operand 2.  OperandType(1), DataType(1), Address(4), bitoffset(1), bitsize(1)
        request_bytes += bytes([2, 0x12, 0x99, 0x88, 0x77, 0x66, 5, 12])
        request_bytes += struct.pack('>Bf', 0, 1.0)  # Operand 3 - OperandType(1), literal(4)
        request_bytes += bytes([3])  # nb_signals
        request_bytes += bytes([0, 0x55, 0x44, 0x33, 0x22, 4])  # Signal 1 - SignalType(1), address(4), size(1)
        request_bytes += bytes([2])  # Signal 2 - SignalType(1)
        request_bytes += bytes([1, 0xab, 0xcd])  # Signal 3 - SignalType(1) RpvId(2)

        self.assert_req_response_bytes(req, request_bytes)
        data = self.proto.parse_request(req)
        self.check_expected_payload_size(req, 0)

        self.assertIn('loop_id', data)
        self.assertIn('config_id', data)
        self.assertIn('config', data)

        data = cast(protocol_typing.Request.DatalogControl.Configure, data)
        self.assertEqual(data['loop_id'], 1)
        self.assertEqual(data['config_id'], 0xaabb)
        config2 = data['config']

        self.assertEqual(config.decimation, config2.decimation)
        self.assertAlmostEqual(config.probe_location, config2.probe_location, 2)
        self.assertEqual(config.timeout, config2.timeout)
        self.assertEqual(config.trigger_hold_time, config2.trigger_hold_time)
        self.assertEqual(config.trigger_condition.condition_id, config2.trigger_condition.condition_id)

        operands = config.trigger_condition.get_operands()
        operands2 = config2.trigger_condition.get_operands()

        self.assertEqual(len(operands), len(operands2))
        for i in range(len(operands)):
            operand = operands[i]
            operand2 = operands2[i]

            self.assertEqual(operand.get_type(), operand2.get_type())

            if isinstance(operand, device_datalogging.LiteralOperand):
                assert isinstance(operand2, device_datalogging.LiteralOperand)
                self.assertEqual(operand.value, operand2.value)
            elif isinstance(operand, device_datalogging.RPVOperand):
                assert isinstance(operand2, device_datalogging.RPVOperand)
                self.assertEqual(operand.rpv_id, operand2.rpv_id)
            elif isinstance(operand, device_datalogging.VarOperand):
                assert isinstance(operand2, device_datalogging.VarOperand)
                self.assertEqual(operand.address, operand2.address)
                self.assertEqual(operand.datatype, operand2.datatype)
            elif isinstance(operand, device_datalogging.VarBitOperand):
                assert isinstance(operand2, device_datalogging.VarBitOperand)
                self.assertEqual(operand.address, operand2.address)
                self.assertEqual(operand.datatype, operand2.datatype)
                self.assertEqual(operand.bitoffset, operand2.bitoffset)
                self.assertEqual(operand.bitsize, operand2.bitsize)
            else:
                raise ValueError("Unknown signal type %s" % (signal.__class__.__name__))

        signals = config.get_signals()
        signals2 = config2.get_signals()
        self.assertEqual(len(signals), len(signals2))
        for i in range(len(signals)):
            signal = signals[i]
            signal2 = signals2[i]

            self.assertEqual(signal.get_type(), signal2.get_type())

            if isinstance(signal, device_datalogging.MemoryLoggableSignal):
                assert isinstance(signal2, device_datalogging.MemoryLoggableSignal)
                self.assertEqual(signal.address, signal2.address)
                self.assertEqual(signal.size, signal2.size)
            elif isinstance(signal, device_datalogging.RPVLoggableSignal):
                assert isinstance(signal2, device_datalogging.RPVLoggableSignal)
                self.assertEqual(signal.rpv_id, signal2.rpv_id)
            elif isinstance(signal, device_datalogging.TimeLoggableSignal):
                assert isinstance(signal2, device_datalogging.TimeLoggableSignal)
            else:
                raise ValueError("Unknown signal type %s" % (signal.__class__.__name__))

    def test_req_datalogging_arm_trigger(self):
        request_bytes = bytes([5, 3, 0, 0])
        req = self.proto.datalogging_arm_trigger()
        self.assert_req_response_bytes(req, request_bytes)
        data = self.proto.parse_request(req)
        self.check_expected_payload_size(req, 0)

    def test_req_datalogging_disarm_trigger(self):
        request_bytes = bytes([5, 4, 0, 0])
        req = self.proto.datalogging_disarm_trigger()
        self.assert_req_response_bytes(req, request_bytes)
        data = self.proto.parse_request(req)
        self.check_expected_payload_size(req, 0)

    def test_req_datalogging_get_status(self):
        request_bytes = bytes([5, 5, 0, 0])
        req = self.proto.datalogging_get_status()
        self.assert_req_response_bytes(req, request_bytes)
        data = self.proto.parse_request(req)
        self.check_expected_payload_size(req, 1)

    def test_req_datalogging_get_acquisition_metadata(self):
        request_bytes = bytes([5, 6, 0, 0])
        req = self.proto.datalogging_get_acquisition_metadata()
        self.assert_req_response_bytes(req, request_bytes)
        data = self.proto.parse_request(req)
        self.check_expected_payload_size(req, 14)

    def test_req_datalogging_read_acquisition(self):
        request_bytes = bytes([5, 7, 0, 0])

        req = self.proto.datalogging_read_acquisition(0, 100, tx_buffer_size=108, encoding=device_datalogging.Encoding.RAW)
        self.assert_req_response_bytes(req, request_bytes)
        data = self.proto.parse_request(req)
        self.check_expected_payload_size(req, 108)

        req = self.proto.datalogging_read_acquisition(0, 100, tx_buffer_size=50, encoding=device_datalogging.Encoding.RAW)
        self.check_expected_payload_size(req, 50)

        req = self.proto.datalogging_read_acquisition(80, 100, tx_buffer_size=100, encoding=device_datalogging.Encoding.RAW)
        self.check_expected_payload_size(req, 28)
# endregion

# region Request UserCommand
    def test_req_user_command(self):
        req = self.proto.user_command(10, bytes([1, 2, 3]))
        self.assert_req_response_bytes(req, [4, 10, 0, 3, 1, 2, 3])
        self.assertEqual(req.subfn, 10)
        self.assertEqual(req.payload, bytes([1, 2, 3]))
        # todo : Response size
# endregion

# ============================
#               Response
# ============================

# region Response GetInfo
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
        response = self.proto.respond_supported_features(memory_read=True, memory_write=False, datalogging=False, user_command=True, _64bits=True)
        self.assert_req_response_bytes(response, [0x81, 3, 0, 0, 1, 0x98])
        data = self.proto.parse_response(response)
        self.assertEqual(data['memory_read'], True)
        self.assertEqual(data['memory_write'], False)
        self.assertEqual(data['datalogging'], False)
        self.assertEqual(data['user_command'], True)
        self.assertEqual(data['_64bits'], True)

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
        self.proto.set_address_size_bits(32)
        rpvs = [
            RuntimePublishedValue(id=0x1234, datatype=EmbeddedDataType.float32),
            RuntimePublishedValue(id=0x9875, datatype=EmbeddedDataType.uint32)
        ]

        definition_payloads = [
            [0x12, 0x34, EmbeddedDataType.float32.value],
            [0x98, 0x75, EmbeddedDataType.uint32.value]
        ]

        response = self.proto.respond_get_rpv_definition(rpvs)
        self.assert_req_response_bytes(response, [0x81, 7, 0, 0, 6] + definition_payloads[0] + definition_payloads[1])
        data = self.proto.parse_response(response)
        self.assertEqual(len(data['rpvs']), 2)
        self.assertEqual(data['rpvs'][0].id, 0x1234)
        self.assertEqual(data['rpvs'][0].datatype, EmbeddedDataType.float32)
        self.assertEqual(data['rpvs'][1].id, 0x9875)
        self.assertEqual(data['rpvs'][1].datatype, EmbeddedDataType.uint32)

    def test_response_get_loop_count(self):
        response = self.proto.respond_get_loop_count(0xAA)
        self.assert_req_response_bytes(response, [0x81, 8, 0, 0, 1, 0xaa])
        data = self.proto.parse_response(response)
        self.assertEqual(data['loop_count'], 0xAA)

    def test_response_get_loop_definition_fixed_freq(self):
        ff_loop = FixedFreqLoop(100, "myloop1", support_datalogging=True)
        response = self.proto.respond_get_loop_definition(0x99, ff_loop)
        payload = bytes([0x81, 9, 0, 0, 15, 0x99, 0x00, 0x80])
        payload += struct.pack('>L', 100000)
        payload += struct.pack('B', 7)
        payload += "myloop1".encode('utf8')
        self.assert_req_response_bytes(response, payload)
        data = self.proto.parse_response(response)
        data = cast(protocol_typing.Response.GetInfo.GetLoopDefinition, data)
        self.assertEqual(data['loop_id'], 0x99)
        self.assertIsInstance(data['loop'], FixedFreqLoop)
        data['loop'] = cast(FixedFreqLoop, data['loop'])
        self.assertFalse(data['loop'] is ff_loop)
        self.assertEqual(data['loop'].get_loop_type(), ExecLoopType.FIXED_FREQ)
        self.assertEqual(data['loop'].get_timestep_100ns(), 100000)
        self.assertEqual(data['loop'].support_datalogging, True)

    def test_response_get_loop_definition_variable_freq(self):
        ff_loop = VariableFreqLoop("myloop2", support_datalogging=False)
        response = self.proto.respond_get_loop_definition(0x88, ff_loop)
        payload = bytes([0x81, 9, 0, 0, 11, 0x88, 0x01, 0x00])
        payload += struct.pack('B', 7)
        payload += "myloop2".encode('utf8')
        self.assert_req_response_bytes(response, payload)
        data = self.proto.parse_response(response)
        data = cast(protocol_typing.Response.GetInfo.GetLoopDefinition, data)
        self.assertEqual(data['loop_id'], 0x88)
        self.assertIsInstance(data['loop'], VariableFreqLoop)
        data['loop'] = cast(VariableFreqLoop, data['loop'])
        self.assertFalse(data['loop'] is ff_loop)
        self.assertEqual(data['loop'].get_loop_type(), ExecLoopType.VARIABLE_FREQ)
        self.assertEqual(data['loop'].support_datalogging, False)


# endregion

# region Response MemoryControl

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
            self.proto.parse_response(response)

        response = Response(cmd.MemoryControl, cmd.MemoryControl.Subfunction.Write,
                            Response.ResponseCode.OK, [0x12, 0x34, 0x56, 0x78, 0x11, 0x22, 0x33])
        with self.assertRaises(Exception):
            self.proto.parse_response(response)

    def test_response_read_single_rpv(self):
        self.proto.configure_rpvs([
            RuntimePublishedValue(id=0x1234, datatype=EmbeddedDataType.float32),
            RuntimePublishedValue(id=0x1235, datatype=EmbeddedDataType.uint16)
        ])

        response = self.proto.respond_read_runtime_published_values((0x1234, 1.123))
        floatdata = [x for x in struct.pack('>f', 1.123)]
        self.assert_req_response_bytes(response, [0x83, 4, 0, 0, 6, 0x12, 0x34] + floatdata)
        data = self.proto.parse_response(response)
        self.assertEqual(data['read_rpv'][0]['id'], 0x1234)
        self.assertEqual(data['read_rpv'][0]['data'], d2f(1.123))

    def test_response_read_multiple_rpv(self):
        self.proto.configure_rpvs([
            RuntimePublishedValue(id=0x1234, datatype=EmbeddedDataType.float32),
            RuntimePublishedValue(id=0x1235, datatype=EmbeddedDataType.uint16)
        ])

        response = self.proto.respond_read_runtime_published_values([(0x1234, 1.123), (0x1235, 0xabcd)])
        floatdata = [x for x in struct.pack('>f', 1.123)]
        self.assert_req_response_bytes(response, [0x83, 4, 0, 0, 10, 0x12, 0x34] + floatdata + [0x12, 0x35, 0xab, 0xcd])
        data = self.proto.parse_response(response)
        self.assertEqual(data['read_rpv'][0]['id'], 0x1234)
        self.assertEqual(data['read_rpv'][0]['data'], d2f(1.123))
        self.assertEqual(data['read_rpv'][1]['id'], 0x1235)
        self.assertEqual(data['read_rpv'][1]['data'], 0xabcd)

    def test_response_read_rpv_bad_datatype(self):
        self.proto.configure_rpvs([
            RuntimePublishedValue(id=0x1234, datatype=EmbeddedDataType.float32),
            RuntimePublishedValue(id=0x1235, datatype=EmbeddedDataType.uint16)
        ])

        with self.assertRaises(Exception):
            self.proto.respond_read_runtime_published_values([(0x1234, 1.123), (0x1235, 1.5)])

    def test_response_read_rpv_unknown_id(self):
        self.proto.configure_rpvs([
            RuntimePublishedValue(id=0x1234, datatype=EmbeddedDataType.float32),
            RuntimePublishedValue(id=0x1235, datatype=EmbeddedDataType.uint16)
        ])

        with self.assertRaises(Exception):
            self.proto.respond_read_runtime_published_values([(0x9999, 1.0)])

    def test_response_write_single_rpv(self):
        self.proto.configure_rpvs([
            RuntimePublishedValue(id=0x1234, datatype=EmbeddedDataType.float32),
            RuntimePublishedValue(id=0x1235, datatype=EmbeddedDataType.uint16)
        ])

        response = self.proto.respond_write_runtime_published_values(0x1234)
        self.assert_req_response_bytes(response, [0x83, 5, 0, 0, 3, 0x12, 0x34, 4])
        data = self.proto.parse_response(response)
        self.assertEqual(data['written_rpv'][0]['id'], 0x1234)
        self.assertEqual(data['written_rpv'][0]['size'], 4)

    def test_response_write_multiple_rpvs(self):
        self.proto.configure_rpvs([
            RuntimePublishedValue(id=0x1234, datatype=EmbeddedDataType.float32),
            RuntimePublishedValue(id=0x1235, datatype=EmbeddedDataType.uint16)
        ])

        response = self.proto.respond_write_runtime_published_values([0x1234, 0x1235])
        self.assert_req_response_bytes(response, [0x83, 5, 0, 0, 6, 0x12, 0x34, 4, 0x12, 0x35, 2])
        data = self.proto.parse_response(response)
        self.assertEqual(data['written_rpv'][0]['id'], 0x1234)
        self.assertEqual(data['written_rpv'][0]['size'], 4)
        self.assertEqual(data['written_rpv'][1]['id'], 0x1235)
        self.assertEqual(data['written_rpv'][1]['size'], 2)

    def test_response_write_rpv_unknown_id(self):
        self.proto.configure_rpvs([
            RuntimePublishedValue(id=0x1234, datatype=EmbeddedDataType.float32),
            RuntimePublishedValue(id=0x1235, datatype=EmbeddedDataType.uint16)
        ])

        with self.assertRaises(Exception):
            self.proto.respond_write_runtime_published_values([0x1234, 0x1235, 0x9999])
# endregion

# region Response CommControl
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
# endregion


# region Response DatalogControl


    def test_response_datalogging_get_setup(self):
        response = self.proto.respond_datalogging_get_setup(buffer_size=0x12345678, encoding=device_datalogging.Encoding.RAW, max_signal_count=32)
        self.assert_req_response_bytes(response, [0x85, 1, 0, 0, 6, 0x12, 0x34, 0x56, 0x78, 0, 32])
        data = self.proto.parse_response(response)
        self.assertEqual(data['buffer_size'], 0x12345678)
        self.assertEqual(data['encoding'], device_datalogging.Encoding.RAW)
        self.assertEqual(data['max_signal_count'], 32)

    def test_response_datalogging_configure(self):
        response = self.proto.respond_datalogging_configure()
        self.assert_req_response_bytes(response, [0x85, 2, 0, 0, 0])
        self.proto.parse_response(response)

    def test_response_datalogging_arm_trigger(self):
        response = self.proto.respond_datalogging_arm_trigger()
        self.assert_req_response_bytes(response, [0x85, 3, 0, 0, 0])
        self.proto.parse_response(response)

    def test_response_datalogging_disarm_trigger(self):
        response = self.proto.respond_datalogging_disarm_trigger()
        self.assert_req_response_bytes(response, [0x85, 4, 0, 0, 0])
        self.proto.parse_response(response)

    def test_response_datalogging_get_status(self):
        response = self.proto.respond_datalogging_get_status(state=device_datalogging.DataloggerState.CONFIGURED)
        self.assert_req_response_bytes(response, [0x85, 5, 0, 0, 1, device_datalogging.DataloggerState.CONFIGURED.value])
        data = self.proto.parse_response(response)
        self.assertEqual(data['state'], device_datalogging.DataloggerState.CONFIGURED)

    def test_response_datalogging_get_acquisition_metadata(self):
        response = self.proto.respond_datalogging_get_acquisition_metadata(
            acquisition_id=0x1234, config_id=0x5678, nb_points=0xaabbccdd, datasize=0x99887766, points_after_trigger=0x1a2b3c4d)
        self.assert_req_response_bytes(response, [0x85, 6, 0, 0, 16, 0x12, 0x34, 0x56, 0x78, 0xaa, 0xbb,
                                       0xcc, 0xdd, 0x99, 0x88, 0x77, 0x66, 0x1a, 0x2b, 0x3c, 0x4d])
        data = self.proto.parse_response(response)
        self.assertEqual(data['acquisition_id'], 0x1234)
        self.assertEqual(data['config_id'], 0x5678)
        self.assertEqual(data['nb_points'], 0xaabbccdd)
        self.assertEqual(data['datasize'], 0x99887766)
        self.assertEqual(data['points_after_trigger'], 0x1a2b3c4d)

    def test_response_datalogging_read_acquisition(self):
        response = self.proto.respond_datalogging_read_acquisition(
            finished=False, rolling_counter=0xAA, acquisition_id=0x1234, data=bytes([1, 2, 3, 4, 5, 6, 7, 8]))
        self.assert_req_response_bytes(response, [0x85, 7, 0, 0, 12, 0, 0xAA, 0x12, 0x34, 1, 2, 3, 4, 5, 6, 7, 8])
        data = self.proto.parse_response(response)
        self.assertEqual(data['finished'], False)
        self.assertEqual(data['rolling_counter'], 0xAA)
        self.assertEqual(data['acquisition_id'], 0x1234)
        self.assertEqual(data['data'], bytes([1, 2, 3, 4, 5, 6, 7, 8]))
        self.assertEqual(data['crc'], None)

        response = self.proto.respond_datalogging_read_acquisition(
            finished=True, rolling_counter=0xAA, acquisition_id=0x1234, data=bytes([1, 2, 3, 4, 5, 6, 7, 8]), crc=0x99887766)
        self.assert_req_response_bytes(response, [0x85, 7, 0, 0, 16, 1, 0xAA, 0x12, 0x34, 1, 2, 3, 4, 5, 6, 7, 8, 0x99, 0x88, 0x77, 0x66])
        data = self.proto.parse_response(response)
        self.assertEqual(data['finished'], True)
        self.assertEqual(data['rolling_counter'], 0xAA)
        self.assertEqual(data['acquisition_id'], 0x1234)
        self.assertEqual(data['data'], bytes([1, 2, 3, 4, 5, 6, 7, 8]))
        self.assertEqual(data['crc'], 0x99887766)

        # CRC must be present if finished. otherwise must not be present
        with self.assertRaises(ValueError):
            self.proto.respond_datalogging_read_acquisition(finished=False, rolling_counter=0xAA,
                                                            acquisition_id=0x1234, data=bytes([1, 2, 3, 4, 5, 6, 7, 8]), crc=0x99887766)
        with self.assertRaises(ValueError):
            self.proto.respond_datalogging_read_acquisition(finished=True, rolling_counter=0xAA,
                                                            acquisition_id=0x1234, data=bytes([1, 2, 3, 4, 5, 6, 7, 8]))

# endregion

# region Response UserCommand

    def test_response_user_cmd(self):
        response = self.proto.respond_user_command(10, bytes([1, 2, 3]))
        self.assert_req_response_bytes(response, [0x84, 10, 0, 0, 3, 1, 2, 3])
        self.assertEqual(response.subfn, 10)
        self.assertEqual(response.payload, bytes([1, 2, 3]))
# endregion


if __name__ == '__main__':
    import unittest
    unittest.main()
