import unittest
import time
import json
import struct

from scrutiny.server.device.emulated_device import EmulatedDevice
from scrutiny.server.server import ScrutinyServer, ServerConfig
from scrutiny.server.api.dummy_client_handler import DummyConnection, DummyClientHandler
from scrutiny.server.api import API
from scrutiny.server.device.device_handler import DeviceHandler
from scrutiny.core.sfd_storage import SFDStorage
from scrutiny.server.datastore.datastore_entry import *
from scrutiny.core.firmware_description import FirmwareDescription
from scrutiny.core.basic_types import *
from scrutiny.core.codecs import *
from test.artifacts import get_artifact
from typing import cast, List, Tuple
from dataclasses import dataclass


def d2f(d):
    return struct.unpack('f', struct.pack('f', d))[0]


class TestServerIntegration(unittest.TestCase):

    entry_float32: DatastoreVariableEntry
    entry_float64: DatastoreVariableEntry
    entry_s8: DatastoreVariableEntry
    entry_u8: DatastoreVariableEntry
    entry_s16: DatastoreVariableEntry
    entry_u16: DatastoreVariableEntry
    entry_s32: DatastoreVariableEntry
    entry_u32: DatastoreVariableEntry
    entry_s64: DatastoreVariableEntry
    entry_u64: DatastoreVariableEntry

    entry_rpv1000: DatastoreRPVEntry
    entry_alias_float32: DatastoreAliasEntry
    entry_alias_int8: DatastoreAliasEntry
    entry_alias_uint8: DatastoreAliasEntry
    entry_alias_rpv1000: DatastoreAliasEntry
    server: ScrutinyServer
    api_conn: DummyConnection
    emulated_device: EmulatedDevice
    sfd: FirmwareDescription
    client_entry_values: Dict[str, any]

    def setUp(self):
        err = None
        try:
            server_config: ServerConfig = {
                'name': "Unit test",
                "api_config": {
                    "client_interface_type": "dummy",
                    "client_interface_config": {}
                },
                "device_config": {
                    'link_type': 'thread_safe_dummy',
                    'link_config': {},
                    'response_timeout': 0.25,
                    'heartbeat_timeout': 2
                },
                "autoload_sfd": False,
            }

            # Server part
            self.server = ScrutinyServer(server_config)
            self.server.init()

            # Device part
            self.emulated_device = EmulatedDevice(self.server.device_handler.get_comm_link())
            self.emulated_device.start()

            # Client part
            self.api_conn = DummyConnection()
            self.api_conn.open()
            cast(DummyClientHandler, self.server.api.get_client_handler()).set_connections([self.api_conn])

            self.wait_for_device_ready()

            self.temp_storage_handler = SFDStorage.use_temp_folder()
            self.load_test_sfd()

            self.client_entry_values = {}

        except Exception as e:
            self.tearDown()
            err = e

        if err:
            raise err

    def load_test_sfd(self):
        SFDStorage.install(get_artifact("test_sfd_1.sfd"))
        self.server.sfd_handler.request_load_sfd('00000000000000000000000000000001')
        self.server.process()
        self.sfd = self.server.sfd_handler.get_loaded_sfd()
        self.assertIsNotNone(self.sfd)
        self.assertEqual(self.sfd.get_firmware_id_ascii(), "00000000000000000000000000000001")

        # Let's make sure that the SFD we loaded matches what this test suite expects

        self.entry_float32 = cast(DatastoreVariableEntry, self.server.datastore.get_entry_by_display_path('/path1/path2/some_float32'))
        self.assert_datastore_variable_entry(self.entry_float32, 1008, EmbeddedDataType.float32)

        self.entry_float64 = cast(DatastoreVariableEntry, self.server.datastore.get_entry_by_display_path('/path1/path2/some_float64'))
        self.assert_datastore_variable_entry(self.entry_float64, 1012, EmbeddedDataType.float64)

        self.entry_s8 = cast(DatastoreVariableEntry, self.server.datastore.get_entry_by_display_path('/path1/path2/some_int8'))
        self.assert_datastore_variable_entry(self.entry_s8, 1020, EmbeddedDataType.sint8)

        self.entry_u8 = cast(DatastoreVariableEntry, self.server.datastore.get_entry_by_display_path('/path1/path2/some_uint8'))
        self.assert_datastore_variable_entry(self.entry_u8, 1021, EmbeddedDataType.uint8)

        self.entry_s16 = cast(DatastoreVariableEntry, self.server.datastore.get_entry_by_display_path('/path1/path2/some_int16'))
        self.assert_datastore_variable_entry(self.entry_s16, 1022, EmbeddedDataType.sint16)

        self.entry_u16 = cast(DatastoreVariableEntry, self.server.datastore.get_entry_by_display_path('/path1/path2/some_uint16'))
        self.assert_datastore_variable_entry(self.entry_u16, 1024, EmbeddedDataType.uint16)

        self.entry_s32 = cast(DatastoreVariableEntry, self.server.datastore.get_entry_by_display_path('/path1/path2/some_int32'))
        self.assert_datastore_variable_entry(self.entry_s32, 1000, EmbeddedDataType.sint32)

        self.entry_u32 = cast(DatastoreVariableEntry, self.server.datastore.get_entry_by_display_path('/path1/path2/some_uint32'))
        self.assert_datastore_variable_entry(self.entry_u32, 1004, EmbeddedDataType.uint32)

        self.entry_s64 = cast(DatastoreVariableEntry, self.server.datastore.get_entry_by_display_path('/path1/path2/some_int64'))
        self.assert_datastore_variable_entry(self.entry_s64, 1032, EmbeddedDataType.sint64)

        self.entry_u64 = cast(DatastoreVariableEntry, self.server.datastore.get_entry_by_display_path('/path1/path2/some_uint64'))
        self.assert_datastore_variable_entry(self.entry_u64, 1040, EmbeddedDataType.uint64)

        self.entry_alias_float32 = cast(DatastoreAliasEntry, self.server.datastore.get_entry_by_display_path('/alias/some_float32'))
        self.assert_datastore_alias_entry(self.entry_alias_float32, '/path1/path2/some_float32',
                                          EmbeddedDataType.float32, gain=2.0, offset=1.0, min=0, max=100.0)

        self.entry_alias_int8 = cast(DatastoreAliasEntry, self.server.datastore.get_entry_by_display_path('/alias/some_int8_overflowable'))
        self.assert_datastore_alias_entry(self.entry_alias_int8, '/path1/path2/some_int8',
                                          EmbeddedDataType.sint8, gain=0.2, offset=1.0, min=-100, max=100.0)

        self.entry_alias_uint8 = cast(DatastoreAliasEntry, self.server.datastore.get_entry_by_display_path('/alias/some_uint8_overflowable'))
        self.assert_datastore_alias_entry(self.entry_alias_uint8, "/path1/path2/some_uint8",
                                          EmbeddedDataType.uint8, gain=0.2, offset=1.0, min=-100, max=100.0)
        self.entry_alias_rpv1000 = cast(DatastoreAliasEntry, self.server.datastore.get_entry_by_display_path('/alias/rpv/rpv1000_f64'))
        self.assert_datastore_alias_entry(self.entry_alias_rpv1000, "/rpv/x1000",
                                          EmbeddedDataType.float64, gain=2.0, offset=1.0, min=-100, max=100.0)

        self.entry_rpv1000 = cast(DatastoreRPVEntry, self.server.datastore.get_entry_by_display_path('/rpv/x1000'))
        self.assert_datastore_rpv_entry(self.entry_rpv1000, 0x1000, EmbeddedDataType.float64)

    def assert_datastore_variable_entry(self, entry: DatastoreVariableEntry, address: int, dtype: EmbeddedDataType):
        self.assertEqual(entry.get_address(), address)
        self.assertEqual(entry.get_data_type(), dtype)

    def assert_datastore_rpv_entry(self, entry: DatastoreRPVEntry, id: int, dtype: EmbeddedDataType):
        self.assertEqual(entry.rpv.datatype, dtype)
        self.assertEqual(entry.rpv.id, id)

    def assert_datastore_alias_entry(self, entry: DatastoreAliasEntry, target: str, dtype: EmbeddedDataType,
                                     min: Optional[float] = None,
                                     max: Optional[float] = None,
                                     gain: Optional[float] = None,
                                     offset: Optional[float] = None):
        self.assertEqual(entry.get_data_type(), dtype)
        self.assertEqual(entry.aliasdef.get_target(), target)

        if min is not None:
            self.assertEqual(entry.aliasdef.min, min)
        if max is not None:
            self.assertEqual(entry.aliasdef.max, max)
        if gain is not None:
            self.assertEqual(entry.aliasdef.gain, gain)
        if offset is not None:
            self.assertEqual(entry.aliasdef.offset, offset)

    def wait_for_device_ready(self, timeout=1.0):
        t1 = time.time()
        self.server.process()
        timed_out = False
        while self.server.device_handler.get_connection_status() != DeviceHandler.ConnectionStatus.CONNECTED_READY:
            if time.time() - t1 >= timeout:
                timed_out = True
                break
            self.server.process()
            time.sleep(0.01)

        if timed_out:
            raise TimeoutError("Timed out while initializing emulated device")

    def wait_for_response(self, timeout=0.4):
        t1 = time.time()
        self.server.process()
        while not self.api_conn.from_server_available():
            if time.time() - t1 >= timeout:
                break
            self.server.process()
            time.sleep(0.01)

        return self.api_conn.read_from_server()

    def wait_for(self, timeout):
        t1 = time.time()
        self.server.process()
        while time.time() - t1 < timeout:
            self.server.process()
            time.sleep(0.01)

    def spinwait_for(self, timeout):
        t1 = time.time()
        self.server.process()
        while time.time() - t1 < timeout:
            self.server.process()

    def wait_and_load_response(self, cmd=None, nbr=1, timeout=0.4):
        response = None
        t1 = time.time()
        rcv_counter = 0
        while rcv_counter < nbr:
            new_timeout = max(0, timeout - (time.time() - t1))
            json_str = self.wait_for_response(timeout=new_timeout)
            self.assertIsNotNone(json_str)
            response = json.loads(json_str)
            if cmd is None:
                rcv_counter += 1
            else:
                if isinstance(cmd, str):
                    cmd = [cmd]
                self.assertIn('cmd', response)
                if response['cmd'] in cmd:
                    rcv_counter += 1

        self.assertIsNotNone(response)
        return response

    def process_watchable_update(self, nbr=None, timeout=None):
        response = None
        if nbr is not None:
            for i in range(nbr):
                response = self.wait_and_load_response(API.Command.Api2Client.WATCHABLE_UPDATE, 1)
                self.process_watchable_update_response(response)
        else:
            t1 = time.time()
            while time.time() - t1 < timeout:
                new_timeout = max(0, timeout - (time.time() - t1))
                response = self.wait_and_load_response(API.Command.Api2Client.WATCHABLE_UPDATE, timeout=new_timeout)
                self.process_watchable_update_response(response)

    def process_watchable_update_response(self, response):
        if response is not None:
            self.assertIn('updates', response)
            for update in response['updates']:
                self.assertIn('id', update)
                self.assertIn('value', update)

                self.client_entry_values[update['id']] = update['value']

    def assert_value_received(self, entry: DatastoreEntry, value: any, msg=""):
        id = entry.get_id()
        self.assertIn(id, self.client_entry_values, msg)
        self.assertEqual(self.client_entry_values[id], value, msg)

    def send_request(self, req):
        self.api_conn.write_to_server(json.dumps(req))

    def assert_no_error(self, response, msg=None):
        self.assertIsNotNone(response)
        if 'cmd' in response:
            if 'msg' in response and msg is None:
                msg = response['msg']
            self.assertNotEqual(response['cmd'], API.Command.Api2Client.ERROR_RESPONSE, msg)

    def assert_is_error(self, response, msg=""):
        if 'cmd' in response:
            self.assertEqual(response['cmd'], API.Command.Api2Client.ERROR_RESPONSE, msg)
        else:
            raise Exception('Missing cmd field in response')

    def assert_watchable_update_response(self, response, expected_list: List[Tuple[DatastoreEntry, Encodable]]):
        self.assertEqual(response['cmd'], API.Command.Api2Client.WATCHABLE_UPDATE)
        self.assertIn('updates', response)

        self.assertEqual(len(expected_list), len(response['updates']))
        ids = [update['id'] for update in response['updates']]
        value = [update['value'] for update in response['updates']]
        valdict = dict(zip(ids, value))

        for expected in expected_list:
            self.assertIn(expected[0].get_id(), valdict)
            self.assertEqual(valdict[expected[0].get_id()], expected[1])

    def read_device_var_entry(self, entry: DatastoreVariableEntry):
        return self.emulated_device.read_memory(entry.get_address(), entry.get_data_type().get_size_byte())

    def read_device_rpv_entry(self, entry: DatastoreRPVEntry):
        return self.emulated_device.rpvs[entry.rpv.id]['value']

    def init_device_memory(self, entries: List[DatastoreEntry]):
        for entry in entries:
            if isinstance(entry, DatastoreVariableEntry):
                self.emulated_device.write_memory(entry.get_address(), b'\x00' * entry.get_size())

    def test_setup_is_working(self):
        # Make sure that the emulation chain works
        self.server.process()
        self.assertEqual(self.server.device_handler.get_connection_status(), DeviceHandler.ConnectionStatus.CONNECTED_READY)
        self.send_request({'cmd': "echo", 'payload': "hello world"})
        response = self.wait_and_load_response()
        self.assert_no_error(response)
        self.assertIn('payload', response)
        self.assertEqual(response['payload'], "hello world")

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
        self.process_watchable_update(nbr=len(all_entries) * 3)
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
        self.process_watchable_update(nbr=len(all_entries) * 3)
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
        self.process_watchable_update(nbr=len(all_entries) * 3)
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
        self.process_watchable_update(nbr=len(all_entries) * 3)
        self.assert_value_received(self.entry_rpv1000, (-100 - 1) / 2)
        self.assert_value_received(self.entry_alias_rpv1000, -100)

    def test_write_oob_values(self):
        @dataclass
        class Testcase:
            entry: DatastoreEntry
            inval: any
            outval: Optional[Encodable]
            valid: bool

            def __repr__(self):
                return "<Testcase entry=<%s:%s>, inval=%s, outval=%s, valid=%s>" % (
                    self.entry.__class__.__name__,
                    self.entry.get_display_path(),
                    self.inval,
                    self.outval,
                    self.valid
                )

        testcases: List[Testcase] = [
            Testcase(entry=self.entry_s8, inval=-25, outval=-25, valid=True),
            Testcase(entry=self.entry_s8, inval=0x100, outval=0x7F, valid=True),
            Testcase(entry=self.entry_s8, inval=-150, outval=-0x80, valid=True),
            Testcase(entry=self.entry_s8, inval=math.inf, outval=None, valid=False),
            Testcase(entry=self.entry_s8, inval=-math.inf, outval=None, valid=False),
            Testcase(entry=self.entry_s8, inval=math.nan, outval=None, valid=False),
            Testcase(entry=self.entry_s8, inval="meow", outval=None, valid=False),
            Testcase(entry=self.entry_s8, inval=None, outval=None, valid=False),

            Testcase(entry=self.entry_u8, inval=50, outval=50, valid=True),
            Testcase(entry=self.entry_u8, inval=0x101, outval=0xFF, valid=True),
            Testcase(entry=self.entry_u8, inval=-150, outval=0, valid=True),
            Testcase(entry=self.entry_u8, inval=math.inf, outval=None, valid=False),
            Testcase(entry=self.entry_u8, inval=-math.inf, outval=None, valid=False),
            Testcase(entry=self.entry_u8, inval=math.nan, outval=None, valid=False),
            Testcase(entry=self.entry_u8, inval="meow", outval=None, valid=False),
            Testcase(entry=self.entry_u8, inval=None, outval=None, valid=False),

            Testcase(entry=self.entry_s16, inval=-1000, outval=-1000, valid=True),
            Testcase(entry=self.entry_s16, inval=0x10000, outval=0x7FFF, valid=True),
            Testcase(entry=self.entry_s16, inval=-0x10000, outval=-0x8000, valid=True),

            Testcase(entry=self.entry_u16, inval=1000, outval=1000, valid=True),
            Testcase(entry=self.entry_u16, inval=0x10000, outval=0xFFFF, valid=True),
            Testcase(entry=self.entry_u16, inval=-0x10000, outval=0, valid=True),

            Testcase(entry=self.entry_s32, inval=-100000, outval=-100000, valid=True),
            Testcase(entry=self.entry_s32, inval=0x100000000, outval=0x7FFFFFFF, valid=True),
            Testcase(entry=self.entry_s32, inval=-0x100000000, outval=-0x80000000, valid=True),

            Testcase(entry=self.entry_u32, inval=100000, outval=100000, valid=True),
            Testcase(entry=self.entry_u32, inval=0x100000000, outval=0xFFFFFFFF, valid=True),
            Testcase(entry=self.entry_u32, inval=-0x100000000, outval=0, valid=True),

            Testcase(entry=self.entry_s64, inval=-10000000, outval=-10000000, valid=True),
            Testcase(entry=self.entry_s64, inval=0x10000000000000000, outval=0x7FFFFFFFFFFFFFFF, valid=True),
            Testcase(entry=self.entry_s64, inval=-0x10000000000000000, outval=-0x8000000000000000, valid=True),

            Testcase(entry=self.entry_u64, inval=10000000, outval=10000000, valid=True),
            Testcase(entry=self.entry_u64, inval=0x10000000000000000, outval=0xFFFFFFFFFFFFFFFF, valid=True),
            Testcase(entry=self.entry_u64, inval=-0x10000000000000000, outval=0, valid=True),

            Testcase(entry=self.entry_alias_int8, inval=10, outval=10, valid=True),
            Testcase(entry=self.entry_alias_int8, inval=-10, outval=-10, valid=True),
            Testcase(entry=self.entry_alias_int8, inval=50, outval=0x7F * 0.2 + 1, valid=True),
            Testcase(entry=self.entry_alias_int8, inval=-50, outval=-0x80 * 0.2 + 1, valid=True),

            Testcase(entry=self.entry_alias_uint8, inval=10, outval=10, valid=True),
            Testcase(entry=self.entry_alias_uint8, inval=100, outval=0xFF * 0.2 + 1, valid=True),
            Testcase(entry=self.entry_alias_uint8, inval=-10, outval=0 * 0.2 + 1, valid=True),
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
                self.process_watchable_update(nbr=len(all_entries) * 3)
                self.assert_value_received(testcase.entry, testcase.outval, msg=assert_msg)

    def tearDown(self) -> None:
        self.emulated_device.stop()
        self.server.stop()
        self.temp_storage_handler.restore()
