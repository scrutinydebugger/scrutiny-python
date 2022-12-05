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


class TestServerIntegration(unittest.TestCase):

    entry_s32_1:DatastoreVariableEntry
    entry_u32_1:DatastoreVariableEntry
    entry_float32_1:DatastoreVariableEntry
    entry_float64_1:DatastoreVariableEntry
    server:ScrutinyServer
    api_conn:DummyConnection
    emulated_device:EmulatedDevice
    sfd:FirmwareDescription

    def setUp(self):
        err = None
        try:
            server_config:ServerConfig = {
                'name' : "Unit test",
                "api_config": {
                    "client_interface_type" : "dummy",
                    "client_interface_config" : {}
                },
                "device_config": {
                    'link_type': 'thread_safe_dummy',
                    'link_config': {},
                    'response_timeout': 0.25,
                    'heartbeat_timeout': 2
                },
                "autoload_sfd" : False,
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

        except Exception as e:
            self.tearDown()
            err = e
        
        if err:
            raise AssertionError("Setup failed.", err)  # Todo, add traceback


    def load_test_sfd(self):
        SFDStorage.install(get_artifact("test_sfd_1.sfd"))
        self.server.sfd_handler.request_load_sfd('00000000000000000000000000000001')
        self.server.process()
        self.sfd = self.server.sfd_handler.get_loaded_sfd()
        self.assertIsNotNone(self.sfd)
        self.assertEqual(self.sfd.get_firmware_id_ascii(), "00000000000000000000000000000001")

        self.entry_s32_1 = cast(DatastoreVariableEntry, self.server.datastore.get_entry_by_display_path('/path1/path2/some_int32'))
        self.assertEqual(self.entry_s32_1.get_address(), 1000)
        self.assertEqual(self.entry_s32_1.get_data_type(), EmbeddedDataType.sint32)

        self.entry_u32_1 = cast(DatastoreVariableEntry, self.server.datastore.get_entry_by_display_path('/path1/path2/some_uint32'))
        self.assertEqual(self.entry_u32_1.get_address(), 1004)
        self.assertEqual(self.entry_u32_1.get_data_type(), EmbeddedDataType.uint32)
        
        self.entry_float32_1 = cast(DatastoreVariableEntry, self.server.datastore.get_entry_by_display_path('/path1/path2/some_float32'))
        self.assertEqual(self.entry_float32_1.get_address(), 1008)
        self.assertEqual(self.entry_float32_1.get_data_type(), EmbeddedDataType.float32)

        self.entry_float64_1 = cast(DatastoreVariableEntry, self.server.datastore.get_entry_by_display_path('/path1/path2/some_float64'))
        self.assertEqual(self.entry_float64_1.get_address(), 1012)
        self.assertEqual(self.entry_float64_1.get_data_type(), EmbeddedDataType.float64)
        

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

    def wait_and_load_response(self, cmd=None, timeout=0.4):
        found = False
        response = None
        t1 = time.time()
        while not found:
            new_timeout = max(0, timeout - (time.time()-t1))
            json_str = self.wait_for_response(timeout=new_timeout)
            self.assertIsNotNone(json_str)
            response = json.loads(json_str)
            if cmd is None:
                found=True
            else:
                self.assertIn('cmd', response)
                if cmd == response['cmd']:
                    found=True
        
        self.assertIsNotNone(response)
        return response

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
    
    def assert_watchable_update_response(self, response, expected_list:List[Tuple[DatastoreEntry, Encodable]]):
        self.assertEqual(response['cmd'], 'watchable_update')
        self.assertIn('updates', response)

        self.assertEqual(len(expected_list), len(response['updates']))
        ids = [update['id'] for update in response['updates']]
        value = [update['value'] for update in response['updates']]
        valdict = dict(zip(ids, value))

        for expected in expected_list:
            self.assertIn(expected[0].get_id(), valdict)
            self.assertEqual(valdict[expected[0].get_id()], expected[1])

    def test_setup_is_working(self):
        # Make sure that the emulation chain works
        self.server.process()
        self.assertEqual(self.server.device_handler.get_connection_status(), DeviceHandler.ConnectionStatus.CONNECTED_READY)
        self.send_request({'cmd' : "echo", 'payload' : "hello world"})
        response = self.wait_and_load_response()
        self.assert_no_error(response)
        self.assertIn('payload', response)
        self.assertEqual(response['payload'], "hello world")
    
    def test_read(self):

        subscribe_cmd = {
            'cmd': 'subscribe_watchable',
            'watchables': [self.entry_s32_1.get_id()]
        }

        self.send_request(subscribe_cmd)
        response = self.wait_and_load_response()
        self.assert_no_error(response)

        self.emulated_device.write_memory(self.entry_s32_1.get_address(), struct.pack("<l", 125))
        response= self.wait_and_load_response('watchable_update')
        
        self.assert_watchable_update_response(response, [(self.entry_s32_1, 125)])



    def tearDown(self) -> None:
        self.emulated_device.stop()
        self.server.stop()
        self.temp_storage_handler.restore()