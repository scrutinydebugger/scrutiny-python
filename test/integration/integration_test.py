#    integration_test.py
#        Base class for tests that checks the integration of all the pythons components. They
#        talk to the API and control an emulated device that runs in a thread
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2023 Scrutiny Debugger

import time
import json

from test import ScrutinyUnitTest
from test.artifacts import get_artifact
from scrutiny.server.device.emulated_device import EmulatedDevice
from scrutiny.server.server import ScrutinyServer, ServerConfig
from scrutiny.server.api.dummy_client_handler import DummyConnection, DummyClientHandler
from scrutiny.server.api import API
from scrutiny.server.device.device_handler import DeviceHandler
from scrutiny.core.firmware_description import FirmwareDescription
from scrutiny.core.sfd_storage import SFDStorage
from scrutiny.server.datastore.datastore_entry import *
from scrutiny.core.basic_types import *
from scrutiny.core.codecs import *
from typing import cast, List, Tuple


class ScrutinyIntegrationTest(ScrutinyUnitTest):

    server: ScrutinyServer
    emulated_device: EmulatedDevice
    api_conn: DummyConnection
    prestart_callback: Callable

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.emulated_device = None
        self.server = None
        self.prestart_callback = None

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
                    'response_timeout': 1,
                    'heartbeat_timeout': 2
                },
                "autoload_sfd": False,
            }

            self.server = ScrutinyServer(server_config)
            self.emulated_device = EmulatedDevice(self.server.device_handler.get_comm_link())
            self.api_conn = DummyConnection()

            if self.prestart_callback is not None:
                self.prestart_callback()

            self.server.init()  # Server
            self.emulated_device.start()    # Device
            self.api_conn.open()    # Client
            cast(DummyClientHandler, self.server.api.get_client_handler()).set_connections([self.api_conn])

            self.wait_for_device_ready()

            self.temp_storage_handler = SFDStorage.use_temp_folder()

            self.client_entry_values = {}

        except Exception as e:
            self.tearDown()
            err = e

        if err:
            raise err

    def assert_datastore_variable_entry(self, entry: DatastoreVariableEntry, address: int, dtype: EmbeddedDataType):
        self.assertEqual(entry.get_address(), address)
        self.assertEqual(entry.get_data_type(), dtype)
        entry.get_size()

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

    def empty_api_rx_queue(self):
        self.server.process()
        while self.api_conn.from_server_available():
            self.api_conn.read_from_server()
            self.server.process()
            self.server.process()

    def spinwait_for(self, timeout):
        t1 = time.time()
        self.server.process()
        while time.time() - t1 < timeout:
            self.server.process()

    def wait_and_load_response(self, cmd=None, nbr=1, timeout=0.4, ignore_error=False):
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

                if not ignore_error:
                    if API.Command.Api2Client.ERROR_RESPONSE not in cmd and response['cmd'] == API.Command.Api2Client.ERROR_RESPONSE:
                        return response
                self.assertIn('cmd', response)
                if response['cmd'] in cmd:
                    rcv_counter += 1

        self.assertIsNotNone(response)
        return response

    def ensure_no_response_for(self, timeout=0.4):
        t1 = time.time()
        self.server.process()
        while not self.api_conn.from_server_available():
            if time.time() - t1 >= timeout:
                break
            self.server.process()
            time.sleep(0.01)

        self.assertFalse(self.api_conn.from_server_available())

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

    def assert_value_received(self, entry: DatastoreEntry, value: Any, msg=""):
        id = entry.get_id()
        self.assertIn(id, self.client_entry_values, msg)
        self.assertEqual(self.client_entry_values[id], value, msg)

    def assert_value_never_received(self, entry: DatastoreEntry, msg=""):
        self.assertNotIn(entry.get_id(), self.client_entry_values, msg)

    def send_request(self, req):
        self.api_conn.write_to_server(json.dumps(req))

    def assert_no_error(self, response, msg=None):
        self.assertIsNotNone(response)
        self.assertIn('cmd', response)
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
        return self.emulated_device.read_memory(entry.get_address(), entry.get_data_type().get_size_byte(), check_access_rights=False)

    def read_device_rpv_entry(self, entry: DatastoreRPVEntry):
        return self.emulated_device.read_rpv(entry.rpv.id)

    def do_test_setup_is_working(self):
        # Make sure that the emulation chain works
        self.server.process()
        self.assertEqual(self.server.device_handler.get_connection_status(), DeviceHandler.ConnectionStatus.CONNECTED_READY)
        self.send_request({'cmd': "echo", 'payload': "hello world"})
        response = self.wait_and_load_response()
        self.assert_no_error(response)
        self.assertIn('payload', response)
        self.assertEqual(response['payload'], "hello world")

    def tearDown(self) -> None:
        if self.emulated_device is not None:
            self.emulated_device.stop()

        if self.server is not None:
            self.server.stop()

        if hasattr(self, 'temp_storage_handler'):
            self.temp_storage_handler.restore()


class ScrutinyIntegrationTestWithTestSFD1(ScrutinyIntegrationTest):

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

    entry_u64_bit15_35: DatastoreVariableEntry

    entry_rpv1000: DatastoreRPVEntry
    entry_alias_float32: DatastoreAliasEntry
    entry_alias_int8: DatastoreAliasEntry
    entry_alias_uint8: DatastoreAliasEntry
    entry_alias_rpv1000: DatastoreAliasEntry
    entry_alias_uint64_15_35: DatastoreAliasEntry

    sfd: FirmwareDescription

    def setUp(self):
        super().setUp()
        self.load_test_sfd()
        return

    def load_test_sfd(self):
        SFDStorage.install(get_artifact("test_sfd_1.sfd"))
        self.server.sfd_handler.request_load_sfd('00000000000000000000000000000001')
        self.server.process()
        self.sfd = self.server.sfd_handler.get_loaded_sfd()
        self.assertEqual(self.sfd.get_endianness(), Endianness.Little)
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

        self.entry_u64_bit15_35 = cast(DatastoreVariableEntry, self.server.datastore.get_entry_by_display_path(
            '/path1/path2/some_uint64_bitfield_15_35'))
        self.assert_datastore_variable_entry(self.entry_u64_bit15_35, 1040, EmbeddedDataType.uint64)
        self.assertTrue(self.entry_u64_bit15_35.is_bitfield())
        self.assertEqual(self.entry_u64_bit15_35.get_bitoffset(), 15)
        self.assertEqual(self.entry_u64_bit15_35.get_bitsize(), 21)

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

        self.entry_alias_uint64_15_35 = cast(DatastoreAliasEntry, self.server.datastore.get_entry_by_display_path('/alias/bitfields/uint64_15_35'))
        self.assert_datastore_alias_entry(self.entry_alias_uint64_15_35, "/path1/path2/some_uint64_bitfield_15_35",
                                          EmbeddedDataType.uint64, gain=2.0, offset=1.0)

        self.entry_rpv1000 = cast(DatastoreRPVEntry, self.server.datastore.get_entry_by_display_path('/rpv/x1000'))
        self.assert_datastore_rpv_entry(self.entry_rpv1000, 0x1000, EmbeddedDataType.float64)


if __name__ == '__main__':
    import unittest
    unittest.main()
