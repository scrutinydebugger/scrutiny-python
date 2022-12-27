#    integration_test.py
#        Base class for tests that checks the integration of all the pythons components. They
#        talk to the API and control an emulated device that runs in a thread
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import unittest
import time
import json

from scrutiny.server.device.emulated_device import EmulatedDevice
from scrutiny.server.server import ScrutinyServer, ServerConfig
from scrutiny.server.api.dummy_client_handler import DummyConnection, DummyClientHandler
from scrutiny.server.api import API
from scrutiny.server.device.device_handler import DeviceHandler
from scrutiny.core.sfd_storage import SFDStorage
from scrutiny.server.datastore.datastore_entry import *
from scrutiny.core.basic_types import *
from scrutiny.core.codecs import *
from typing import cast, List, Tuple


class ScrutinyIntegrationTest(unittest.TestCase):
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

    def tearDown(self) -> None:
        self.emulated_device.stop()
        self.server.stop()
        if hasattr(self, 'temp_storage_handler'):
            self.temp_storage_handler.restore()
