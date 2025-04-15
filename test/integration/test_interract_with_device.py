#    test_interract_with_device.py
#        Make sure we can do some API calls related to the device that are not read/writes.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny.server.api import API
from scrutiny.server.api import typing as api_typing
from scrutiny.core.basic_types import *
import functools
from typing import *
import time

from test.integration.integration_test import ScrutinyIntegrationTestWithTestSFD1


class TestInterractWithDevice(ScrutinyIntegrationTestWithTestSFD1):

    def setUp(self):
        def setup_regions(self: "TestInterractWithDevice"):
            self.emulated_device.add_forbidden_region(0x1000, 0x100)
            self.emulated_device.add_forbidden_region(0x3000, 0x200)
            self.emulated_device.add_readonly_region(0x10000, 0x300)
            self.emulated_device.add_readonly_region(0x15000, 0x400)
        self.prestart_callback = functools.partial(setup_regions, self)

        return super().setUp()

    def test_read_device_info(self):
        self.send_request({
            'cmd': API.Command.Client2Api.GET_DEVICE_INFO,
        })
        response = self.wait_and_load_response(cmd=API.Command.Api2Client.GET_DEVICE_INFO)
        self.assert_no_error(response)

        self.assertEqual(response['available'], True)
        self.assertIsNotNone(response['device_info'])
        self.assertEqual(response['device_info']['device_id'], self.emulated_device.get_firmware_id_ascii())
        self.assertEqual(response['device_info']['display_name'], self.emulated_device.display_name)
        self.assertEqual(response['device_info']['max_rx_data_size'], self.emulated_device.max_rx_data_size)
        self.assertEqual(response['device_info']['max_tx_data_size'], self.emulated_device.max_tx_data_size)
        self.assertEqual(response['device_info']['max_bitrate_bps'], self.emulated_device.max_bitrate_bps)
        self.assertEqual(response['device_info']['rx_timeout_us'], self.emulated_device.rx_timeout_us)
        self.assertEqual(response['device_info']['heartbeat_timeout_us'], self.emulated_device.heartbeat_timeout_us)
        self.assertEqual(response['device_info']['address_size_bits'], self.emulated_device.address_size_bits)
        self.assertEqual(response['device_info']['protocol_major'], self.emulated_device.protocol.version_major)
        self.assertEqual(response['device_info']['protocol_minor'], self.emulated_device.protocol.version_minor)
        self.assertEqual(response['device_info']['supported_feature_map']['memory_write'], self.emulated_device.supported_features['memory_write'])
        self.assertEqual(response['device_info']['supported_feature_map']['datalogging'], self.emulated_device.supported_features['datalogging'])
        self.assertEqual(response['device_info']['supported_feature_map']['user_command'], self.emulated_device.supported_features['user_command'])
        self.assertEqual(response['device_info']['supported_feature_map']['_64bits'], self.emulated_device.supported_features['_64bits'])

        self.assertEqual(len(response['device_info']['readonly_memory_regions']), 2)
        self.assertEqual(response['device_info']['readonly_memory_regions'][0]['start'], 0x10000)
        self.assertEqual(response['device_info']['readonly_memory_regions'][0]['size'], 0x300)
        self.assertEqual(response['device_info']['readonly_memory_regions'][0]['end'], 0x102FF)
        self.assertEqual(response['device_info']['readonly_memory_regions'][1]['start'], 0x15000)
        self.assertEqual(response['device_info']['readonly_memory_regions'][1]['size'], 0x400)
        self.assertEqual(response['device_info']['readonly_memory_regions'][1]['end'], 0x153FF)

        self.assertEqual(len(response['device_info']['forbidden_memory_regions']), 2)
        self.assertEqual(response['device_info']['forbidden_memory_regions'][0]['start'], 0x1000)
        self.assertEqual(response['device_info']['forbidden_memory_regions'][0]['size'], 0x100)
        self.assertEqual(response['device_info']['forbidden_memory_regions'][0]['end'], 0x10FF)
        self.assertEqual(response['device_info']['forbidden_memory_regions'][1]['start'], 0x3000)
        self.assertEqual(response['device_info']['forbidden_memory_regions'][1]['size'], 0x200)
        self.assertEqual(response['device_info']['forbidden_memory_regions'][1]['end'], 0x31FF)
    

    def test_read_status(self):
        self.send_request({
            'cmd': API.Command.Client2Api.GET_SERVER_STATUS,
            'reqid': 123
        })
        timeout = 3
        t = time.monotonic()
        while time.monotonic()-t < timeout:
            response = self.wait_and_load_response(cmd=API.Command.Api2Client.INFORM_SERVER_STATUS)
            self.assert_no_error(response)
            response = cast(api_typing.S2C.InformServerStatus, response)
            
            if response['reqid'] == 123:
                break

        self.assertEqual(response['reqid'], 123)
        self.assertEqual(response['device_status'], 'connected_ready')
        self.assertEqual(response['device_session_id'], self.server.device_handler.get_comm_session_id())

        self.assertIn(response['device_datalogging_status']['datalogger_state'], ['standby', 'unavailable'])
        self.assertEqual(response['device_datalogging_status']['completion_ratio'], None)
        loaded_sfd = self.server.sfd_handler.get_loaded_sfd()
        self.assertEqual(response['loaded_sfd_firmware_id'], loaded_sfd.get_firmware_id_ascii())


    def test_get_loaded_sfd(self):
        self.send_request({
            'cmd': API.Command.Client2Api.GET_LOADED_SFD,
        })
        response = self.wait_and_load_response(cmd=API.Command.Api2Client.GET_LOADED_SFD_RESPONSE)
        self.assert_no_error(response)

        response = cast(api_typing.S2C.GetLoadedSFD, response)

        loaded_sfd = self.server.sfd_handler.get_loaded_sfd()
        self.assertEqual(response['firmware_id'], loaded_sfd.get_firmware_id_ascii())

        self.assertEqual(response['metadata']['author'], loaded_sfd.metadata.author)
        self.assertEqual(response['metadata']['project_name'], loaded_sfd.metadata.project_name)
        self.assertEqual(response['metadata']['version'], loaded_sfd.metadata.version)
        self.assertEqual(response['metadata']['generation_info']['python_version'],
                         loaded_sfd.metadata.generation_info.python_version)
        self.assertEqual(response['metadata']['generation_info']['scrutiny_version'],
                         loaded_sfd.metadata.generation_info.scrutiny_version)
        self.assertEqual(response['metadata']['generation_info']['system_type'], loaded_sfd.metadata.generation_info.system_type)
        self.assertEqual(response['metadata']['generation_info']['time'], loaded_sfd.metadata.generation_info.timestamp.timestamp())

class TestInterractWithDeviceNoThrottling(ScrutinyIntegrationTestWithTestSFD1):

    def setUp(self):
        def setup_bitrate(self: "TestInterractWithDevice"):
            self.emulated_device.max_bitrate_bps = 0
        self.prestart_callback = functools.partial(setup_bitrate, self)
        return super().setUp()

    def test_read_status(self):
        self.send_request({
            'cmd': API.Command.Client2Api.GET_DEVICE_INFO,
        })
        response = self.wait_and_load_response(cmd=API.Command.Api2Client.GET_DEVICE_INFO)
        self.assert_no_error(response)

        response = cast(api_typing.S2C.GetDeviceInfo, response)

        self.assertEqual(response['device_info']['max_bitrate_bps'], None)
