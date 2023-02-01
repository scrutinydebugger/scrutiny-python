#    test_read_write.py
#        Does some Read and Write through the API and check the memory of the emulated device
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2023 Scrutiny Debugger

import struct

from scrutiny.server.api import API
from scrutiny.server.datastore.datastore_entry import *
from scrutiny.core.basic_types import *
from scrutiny.core.codecs import *
from typing import List
from dataclasses import dataclass
from binascii import unhexlify

from test.integration.integration_test import ScrutinyIntegrationTestWithTestSFD1


def d2f(d):
    return struct.unpack('f', struct.pack('f', d))[0]


class TestReadWrite(ScrutinyIntegrationTestWithTestSFD1):

    client_entry_values: Dict[str, Any]

    def init_device_memory(self, entries: List[DatastoreEntry]):
        for entry in entries:
            if isinstance(entry, DatastoreVariableEntry):
                self.emulated_device.write_memory(entry.get_address(), b'\x00' * entry.get_size())

    def test_setup_is_working(self):
        self.do_test_setup_is_working()

    def test_read(self):

        all_entries = [self.entry_s32]
        self.init_device_memory(all_entries)

        subscribe_cmd = {
            'cmd': API.Command.Client2Api.SUBSCRIBE_WATCHABLE,
            'watchables': [entry.get_id() for entry in all_entries]
        }

        self.send_request(subscribe_cmd)
        response = self.wait_and_load_response()
        self.assert_no_error(response)

        self.emulated_device.write_memory(self.entry_s32.get_address(), struct.pack("<l", 125))
        self.process_watchable_update(nbr=2)
        self.assert_value_received(self.entry_s32, 125)

        self.emulated_device.write_memory(self.entry_s32.get_address(), struct.pack("<l", 130))
        self.wait_and_load_response(API.Command.Api2Client.WATCHABLE_UPDATE)  # Make sure to avoid race conditions
        self.process_watchable_update(nbr=2)
        self.assert_value_received(self.entry_s32, 130)

    def test_write_read(self):
        all_entries: List[DatastoreEntry] = [self.entry_float32, self.entry_alias_float32, self.entry_rpv1000, self.entry_alias_rpv1000]
        self.init_device_memory(all_entries)

        subscribe_cmd = {
            'cmd': API.Command.Client2Api.SUBSCRIBE_WATCHABLE,
            # One of each type
            'watchables': [entry.get_id() for entry in all_entries]
        }

        self.send_request(subscribe_cmd)
        response = self.wait_and_load_response()
        self.assert_no_error(response)

        self.emulated_device.write_memory(self.entry_float32.get_address(), struct.pack("<f", d2f(-3.1415926)))
        self.process_watchable_update(nbr=len(all_entries) * 2)
        self.assert_value_received(self.entry_float32, d2f(-3.1415926))

        # Write f32 var
        write_req = {
            'cmd': API.Command.Client2Api.WRITE_VALUE,
            'updates': [dict(watchable=self.entry_float32.get_id(), value=d2f(999.99))]
        }

        self.send_request(write_req)
        self.wait_for(0.1)

        new_val = struct.unpack('<f', self.read_device_var_entry(self.entry_float32))[0]
        self.assertEqual(new_val, d2f(999.99))
        self.empty_api_rx_queue()
        self.process_watchable_update(nbr=len(all_entries) * 2)
        self.assert_value_received(self.entry_float32, d2f(999.99))
        self.assert_value_received(self.entry_alias_float32, d2f(d2f(999.99) * 2 + 1))

        # Write f32 alias
        # Max 100. Gain 2, offset 1
        # Alias min/max applies only in write
        write_req = {
            'cmd': API.Command.Client2Api.WRITE_VALUE,
            'updates': [dict(watchable=self.entry_alias_float32.get_id(), value=d2f(888.88))]
        }

        self.send_request(write_req)
        self.wait_for(0.1)

        new_val = struct.unpack('<f', self.read_device_var_entry(self.entry_float32))[0]
        self.assertEqual(new_val, d2f(100 - 1) / 2)
        self.empty_api_rx_queue()
        self.process_watchable_update(nbr=len(all_entries) * 2)
        self.assert_value_received(self.entry_float32, d2f((100 - 1) / 2))
        self.assert_value_received(self.entry_alias_float32, d2f(100))

        # Write f64 RPV
        write_req = {
            'cmd': API.Command.Client2Api.WRITE_VALUE,
            'updates': [dict(watchable=self.entry_rpv1000.get_id(), value=math.sqrt(3))]
        }

        self.send_request(write_req)
        self.wait_for(0.1)

        self.assertEqual(self.read_device_rpv_entry(self.entry_rpv1000), math.sqrt(3))
        self.empty_api_rx_queue()
        self.process_watchable_update(nbr=len(all_entries) * 2)
        self.assert_value_received(self.entry_rpv1000, math.sqrt(3))
        self.assert_value_received(self.entry_alias_rpv1000, (math.sqrt(3) * 2 + 1))

        # Write f64 RPV Alias. Min -100. Gain 2. Offset 1
        # Alias min/max applies only in write
        write_req = {
            'cmd': API.Command.Client2Api.WRITE_VALUE,
            'updates': [dict(watchable=self.entry_alias_rpv1000.get_id(), value=-150)]
        }

        self.send_request(write_req)
        self.wait_for(0.1)

        self.assertEqual(self.read_device_rpv_entry(self.entry_rpv1000), (-100 - 1) / 2)
        self.empty_api_rx_queue()
        self.process_watchable_update(nbr=len(all_entries) * 2)
        self.assert_value_received(self.entry_rpv1000, (-100 - 1) / 2)
        self.assert_value_received(self.entry_alias_rpv1000, -100)

    def test_write_read_bitfields(self):
        all_entries: List[DatastoreEntry] = [self.entry_alias_uint64_15_35, self.entry_u64, self.entry_u64_bit15_35]
        self.init_device_memory(all_entries)

        subscribe_cmd = {
            'cmd': API.Command.Client2Api.SUBSCRIBE_WATCHABLE,
            'watchables': [entry.get_id() for entry in all_entries]
        }

        self.send_request(subscribe_cmd)
        response = self.wait_and_load_response()
        self.assert_no_error(response)

        self.emulated_device.write_memory(self.entry_u64.get_address(), unhexlify('AAAAAAAAAAAAAAAA'))
        val = 0x1BB7CF  # 1 1011 1011 0111 1100 1111
        # 00000000 00000000 00000000 00001101 11011011 11100111 10000000 00000000 = 00 00 00 0D DB 80 00

        # Write Bitfield var
        write_req = {
            'cmd': API.Command.Client2Api.WRITE_VALUE,
            'updates': [dict(watchable=self.entry_u64_bit15_35.get_id(), value=val)]
        }

        self.send_request(write_req)
        self.wait_for(0.1)

        u64_data = self.read_device_var_entry(self.entry_u64)
        expected_u64_value = (0xAAAAAAAAAAAAAAAA & 0xFFFFFFF000007FFF) | (val << 15)
        self.assertEqual(u64_data, bytearray([
            (expected_u64_value >> 0) & 0xFF,
            (expected_u64_value >> 8) & 0xFF,
            (expected_u64_value >> 16) & 0xFF,
            (expected_u64_value >> 24) & 0xFF,
            (expected_u64_value >> 32) & 0xFF,
            (expected_u64_value >> 40) & 0xFF,
            (expected_u64_value >> 48) & 0xFF,
            (expected_u64_value >> 56) & 0xFF,
        ]))

        self.empty_api_rx_queue()
        self.process_watchable_update(nbr=len(all_entries) * 2)

        self.assert_value_received(self.entry_u64_bit15_35, val)
        self.assert_value_received(self.entry_alias_uint64_15_35, val * 2 + 1)
        self.assert_value_received(self.entry_u64, expected_u64_value)

    def test_write_oob_values(self):
        #  TODO : To investigate : This test failed once for no apparent reason. There might be a race condition or some sort
        # or timing weakness somewhere in here.
        @dataclass
        class WriteOOBTestcase:
            entry: DatastoreEntry
            inval: any
            outval: Optional[Encodable]
            valid: bool
            additional_checks: Optional[List[Tuple[DatastoreEntry, Encodable]]] = None

            def __repr__(self):
                return "<Testcase entry=<%s:%s>, inval=%s, outval=%s, valid=%s>" % (
                    self.entry.__class__.__name__,
                    self.entry.get_display_path(),
                    self.inval,
                    self.outval,
                    self.valid
                )

        testcases: List[WriteOOBTestcase] = [
            WriteOOBTestcase(entry=self.entry_s8, inval=-25, outval=-25, valid=True),
            WriteOOBTestcase(entry=self.entry_s8, inval=0x100, outval=0x7F, valid=True),
            WriteOOBTestcase(entry=self.entry_s8, inval=-150, outval=-0x80, valid=True),
            WriteOOBTestcase(entry=self.entry_s8, inval=math.inf, outval=None, valid=False),
            WriteOOBTestcase(entry=self.entry_s8, inval=-math.inf, outval=None, valid=False),
            WriteOOBTestcase(entry=self.entry_s8, inval=math.nan, outval=None, valid=False),
            WriteOOBTestcase(entry=self.entry_s8, inval="meow", outval=None, valid=False),
            WriteOOBTestcase(entry=self.entry_s8, inval=None, outval=None, valid=False),

            WriteOOBTestcase(entry=self.entry_u8, inval=50, outval=50, valid=True),
            WriteOOBTestcase(entry=self.entry_u8, inval=0x101, outval=0xFF, valid=True),
            WriteOOBTestcase(entry=self.entry_u8, inval=-150, outval=0, valid=True),
            WriteOOBTestcase(entry=self.entry_u8, inval=math.inf, outval=None, valid=False),
            WriteOOBTestcase(entry=self.entry_u8, inval=-math.inf, outval=None, valid=False),
            WriteOOBTestcase(entry=self.entry_u8, inval=math.nan, outval=None, valid=False),
            WriteOOBTestcase(entry=self.entry_u8, inval="meow", outval=None, valid=False),
            WriteOOBTestcase(entry=self.entry_u8, inval=None, outval=None, valid=False),

            WriteOOBTestcase(entry=self.entry_s16, inval=-1000, outval=-1000, valid=True),
            WriteOOBTestcase(entry=self.entry_s16, inval=0x10000, outval=0x7FFF, valid=True),
            WriteOOBTestcase(entry=self.entry_s16, inval=-0x10000, outval=-0x8000, valid=True),

            WriteOOBTestcase(entry=self.entry_u16, inval=1000, outval=1000, valid=True),
            WriteOOBTestcase(entry=self.entry_u16, inval=0x10000, outval=0xFFFF, valid=True),
            WriteOOBTestcase(entry=self.entry_u16, inval=-0x10000, outval=0, valid=True),

            WriteOOBTestcase(entry=self.entry_s32, inval=-100000, outval=-100000, valid=True),
            WriteOOBTestcase(entry=self.entry_s32, inval=0x100000000, outval=0x7FFFFFFF, valid=True),
            WriteOOBTestcase(entry=self.entry_s32, inval=-0x100000000, outval=-0x80000000, valid=True),

            WriteOOBTestcase(entry=self.entry_u32, inval=100000, outval=100000, valid=True),
            WriteOOBTestcase(entry=self.entry_u32, inval=0x100000000, outval=0xFFFFFFFF, valid=True),
            WriteOOBTestcase(entry=self.entry_u32, inval=-0x100000000, outval=0, valid=True),

            WriteOOBTestcase(entry=self.entry_s64, inval=-10000000, outval=-10000000, valid=True),
            WriteOOBTestcase(entry=self.entry_s64, inval=0x10000000000000000, outval=0x7FFFFFFFFFFFFFFF, valid=True),
            WriteOOBTestcase(entry=self.entry_s64, inval=-0x10000000000000000, outval=-0x8000000000000000, valid=True),

            WriteOOBTestcase(entry=self.entry_u64, inval=10000000, outval=10000000, valid=True),
            WriteOOBTestcase(entry=self.entry_u64, inval=0x10000000000000000, outval=0xFFFFFFFFFFFFFFFF, valid=True),
            WriteOOBTestcase(entry=self.entry_u64, inval=-0x10000000000000000, outval=0, valid=True),

            WriteOOBTestcase(entry=self.entry_alias_int8, inval=10, outval=10, valid=True),
            WriteOOBTestcase(entry=self.entry_alias_int8, inval=-10, outval=-10, valid=True),
            WriteOOBTestcase(entry=self.entry_alias_int8, inval=50, outval=0x7F * 0.2 + 1, valid=True),
            WriteOOBTestcase(entry=self.entry_alias_int8, inval=-50, outval=-0x80 * 0.2 + 1, valid=True),

            WriteOOBTestcase(entry=self.entry_alias_uint8, inval=10, outval=10, valid=True),
            WriteOOBTestcase(entry=self.entry_alias_uint8, inval=100, outval=0xFF * 0.2 + 1, valid=True),
            WriteOOBTestcase(entry=self.entry_alias_uint8, inval=-10, outval=0 * 0.2 + 1, valid=True),

            WriteOOBTestcase(entry=self.entry_u64, inval=0x5555555555555555, outval=0x5555555555555555, valid=True),
            WriteOOBTestcase(entry=self.entry_u64_bit15_35, inval=0xFFFFFFFFFFFFFFFF, outval=0x1FFFFF, valid=True,
                             additional_checks=[(self.entry_u64, 0x5555555FFFFFD555)]
                             ),
            WriteOOBTestcase(entry=self.entry_u64_bit15_35, inval=-1, outval=0, valid=True),
        ]

        all_entries = list(set([tc.entry for tc in testcases]))
        self.init_device_memory(all_entries)

        subscribe_cmd = {
            'cmd': API.Command.Client2Api.SUBSCRIBE_WATCHABLE,
            'watchables': [entry.get_id() for entry in all_entries]
        }

        self.send_request(subscribe_cmd)
        response = self.wait_and_load_response(cmd=API.Command.Api2Client.SUBSCRIBE_WATCHABLE_RESPONSE)
        self.assert_no_error(response)

        reqid = 0
        for testcase in testcases:
            reqid += 1
            req = {
                'cmd': API.Command.Client2Api.WRITE_VALUE,
                'reqid': reqid,
                'updates': [dict(watchable=testcase.entry.get_id(), value=testcase.inval)]
            }

            self.send_request(req)
            response = self.wait_and_load_response([API.Command.Api2Client.WRITE_VALUE_RESPONSE, API.Command.Api2Client.ERROR_RESPONSE])

            assert_msg = "reqid=%d. Testcase=%s" % (reqid, testcase)
            if not testcase.valid:
                self.assert_is_error(response, msg=assert_msg)
            else:
                self.assert_no_error(response, msg=assert_msg)
                self.empty_api_rx_queue()
                self.process_watchable_update(nbr=len(all_entries) * 2)
                self.assert_value_received(testcase.entry, testcase.outval, msg=assert_msg)

                if testcase.additional_checks is not None:
                    for check in testcase.additional_checks:
                        assert_msg = "reqid=%d. Testcase=%s (extra_check:%s=%s)" % (reqid, testcase, check[0].get_display_path(), check[1])
                        self.assert_value_received(check[0], check[1], msg=assert_msg)

    def tearDown(self) -> None:
        super().tearDown()


if __name__ == '__main__':
    import unittest
    unittest.main()
