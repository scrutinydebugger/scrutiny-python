
from scrutiny.server.api import API
from scrutiny.server.api import typing as api_typing
from scrutiny.core.basic_types import *
from typing import *
import functools

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

    def test_read_status(self):
        self.send_request({
            'cmd': API.Command.Client2Api.GET_SERVER_STATUS,
        })
        response = self.wait_and_load_response(cmd=API.Command.Api2Client.INFORM_SERVER_STATUS)
        self.assert_no_error(response)

        response = cast(api_typing.S2C.InformServerStatus, response)

        self.assertEqual(response['device_status'], 'connected_ready')

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

        self.assertEqual(response['device_session_id'], self.server.device_handler.get_comm_session_id())

        self.assertIn(response['device_datalogging_status']['datalogger_state'], ['standby', 'unavailable'])
        self.assertEqual(response['device_datalogging_status']['completion_ratio'], None)
        loaded_sfd = self.server.sfd_handler.get_loaded_sfd()
        self.assertEqual(response['loaded_sfd']['firmware_id'], loaded_sfd.get_firmware_id_ascii())

        self.assertEqual(response['loaded_sfd']['metadata']['author'], loaded_sfd.metadata['author'])
        self.assertEqual(response['loaded_sfd']['metadata']['project_name'], loaded_sfd.metadata['project_name'])
        self.assertEqual(response['loaded_sfd']['metadata']['version'], loaded_sfd.metadata['version'])
        self.assertEqual(response['loaded_sfd']['metadata']['generation_info']['python_version'],
                         loaded_sfd.metadata['generation_info']['python_version'])
        self.assertEqual(response['loaded_sfd']['metadata']['generation_info']['scrutiny_version'],
                         loaded_sfd.metadata['generation_info']['scrutiny_version'])
        self.assertEqual(response['loaded_sfd']['metadata']['generation_info']['system_type'], loaded_sfd.metadata['generation_info']['system_type'])
        self.assertEqual(response['loaded_sfd']['metadata']['generation_info']['time'], loaded_sfd.metadata['generation_info']['time'])
