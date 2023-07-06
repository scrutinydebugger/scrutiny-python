
import unittest

import scrutiny.sdk._api_parser as parser
from scrutiny.core.basic_types import *
from scrutiny.sdk.definitions import *
import scrutiny.sdk.exceptions as sdk_exceptions
from copy import copy
from datetime import datetime


class TestApiParser(unittest.TestCase):
    def test_parse_get_single_watchable(self):
        requested_path = '/a/b/c'

        def base():
            return {
                "cmd": "response_get_watchable_list",
                "reqid": 123,
                "done": True,
                "qty": {"var": 1, "alias": 0, "rpv": 0},
                "content": {
                    "var": [{"id": "theid", "display_path": requested_path, "datatype": "sint32"}],
                    "alias": [],
                    "rpv": []
                }
            }

        res = parser.parse_get_watchable_single_element(base(), requested_path)
        self.assertEqual(res.datatype, EmbeddedDataType.sint32)
        self.assertEqual(res.server_id, 'theid')
        self.assertEqual(res.watchable_type, WatchableType.Variable)

        msg = base()
        msg['content']['alias'] = copy(msg['content']['var'])
        msg['qty']['alias'] = 1
        msg['content']['var'] = []
        msg['qty']['var'] = 0

        res = parser.parse_get_watchable_single_element(msg, requested_path)
        self.assertEqual(res.datatype, EmbeddedDataType.sint32)
        self.assertEqual(res.server_id, 'theid')
        self.assertEqual(res.watchable_type, WatchableType.Alias)

        with self.assertRaises(sdk_exceptions.BadResponseError):
            parser.parse_get_watchable_single_element(base(), 'xxx')

        with self.assertRaises(sdk_exceptions.BadResponseError):
            msg = base()
            msg['done'] = False
            parser.parse_get_watchable_single_element(msg, requested_path)

        with self.assertRaises(sdk_exceptions.NameNotFoundError):
            msg = base()
            msg['qty']['var'] = 0
            parser.parse_get_watchable_single_element(msg, requested_path)

        with self.assertRaises(sdk_exceptions.BadResponseError):
            msg = base()
            msg['qty']['alias'] = 1
            parser.parse_get_watchable_single_element(msg, requested_path)

        with self.assertRaises(sdk_exceptions.BadResponseError):
            msg = base()
            msg['content']['var'].append({'id': 'xxx', "display_path": '/q/w/e', "datatype": "uint32"})
            parser.parse_get_watchable_single_element(msg, requested_path)

        with self.assertRaises(sdk_exceptions.BadResponseError):
            msg = base()
            msg['content']['alias'].append({'id': 'xxx', "display_path": '/q/w/e', "datatype": "uint32"})
            parser.parse_get_watchable_single_element(msg, requested_path)

        with self.assertRaises(sdk_exceptions.BadResponseError):
            msg = base()
            msg['content']['var'][0]['id'] = None
            parser.parse_get_watchable_single_element(msg, requested_path)

        with self.assertRaises(sdk_exceptions.BadResponseError):
            msg = base()
            msg['content']['var'][0]['datatype'] = 'asdas'
            parser.parse_get_watchable_single_element(msg, requested_path)

        with self.assertRaises(sdk_exceptions.BadResponseError):
            msg = base()
            del msg['qty']['rpv']
            parser.parse_get_watchable_single_element(msg, requested_path)

        with self.assertRaises(sdk_exceptions.BadResponseError):
            msg = base()
            del msg['content']['rpv']
            parser.parse_get_watchable_single_element(msg, requested_path)

    def test_parse_inform_Server_Status(self):
        def base():
            return {
                "cmd": "inform_server_status",
                "reqid": 2,
                "device_status": "connected_ready",
                "device_session_id": "3d41973c65ba42218ab65c829a8c385e",
                "device_info": {
                    "device_id": "b5c76f482e39e9d6a9115db5b8b7dc35",
                    "display_name": "TestApp Executable",
                    "max_tx_data_size": 256,
                    "max_rx_data_size": 128,
                    "max_bitrate_bps": 100000,
                    "rx_timeout_us": 50000,
                    "heartbeat_timeout_us": 5000000,
                    "address_size_bits": 64,
                    "protocol_major": 1,
                    "protocol_minor": 0,
                    "supported_feature_map": {
                        "memory_read": True,
                        "memory_write": True,
                        "datalogging": True,
                        "user_command": False,
                        "_64bits": True
                    },
                    "forbidden_memory_regions": [{'start': 0x1000, 'end': 0x1FFF}, {'start': 0x4000, 'end': 0x4FFF}],
                    "readonly_memory_regions": [{'start': 0x8000, 'end': 0x8FFF}]
                },
                "loaded_sfd": {
                    "firmware_id": "b5c76f482e39e9d6a9115db5b8b7dc35",
                    "metadata": {
                        "project_name": "Some project",
                        "author": "unit test",
                        "version": "1.2.3",
                        "generation_info": {
                            "time": 1688431050,
                            "python_version": "3.10.5",
                            "scrutiny_version": "0.0.1",
                            "system_type": "Linux"
                        }
                    }
                },
                "device_datalogging_status": {
                    "datalogger_state": "standby",
                    "completion_ratio": 0.56
                },
                "device_comm_link": {
                    "link_type": "udp",
                    "link_config": {
                        "host": "localhost",
                        "port": 12345
                    }
                }
            }

        msg = base()
        info = parser.parse_inform_server_status(msg)

        self.assertEqual(info.device_comm_state, DeviceCommState.ConnectedReady)
        self.assertEqual(info.device_session_id, "3d41973c65ba42218ab65c829a8c385e")

        self.assertIsNotNone(info.device)
        self.assertEqual(info.device.device_id, "b5c76f482e39e9d6a9115db5b8b7dc35")
        self.assertEqual(info.device.display_name, "TestApp Executable")
        self.assertEqual(info.device.max_tx_data_size, 256)
        self.assertEqual(info.device.max_rx_data_size, 128)
        self.assertEqual(info.device.max_bitrate_bps, 100000)
        self.assertEqual(info.device.rx_timeout_us, 50000)
        self.assertEqual(info.device.heartbeat_timeout, 5)
        self.assertEqual(info.device.address_size_bits, 64)
        self.assertEqual(info.device.protocol_major, 1)
        self.assertEqual(info.device.protocol_minor, 0)
        self.assertEqual(info.device.supported_features.memory_write, True)
        self.assertEqual(info.device.supported_features.datalogging, True)
        self.assertEqual(info.device.supported_features.user_command, False)
        self.assertEqual(info.device.supported_features.sixtyfour_bits, True)

        self.assertIsNotNone(info.sfd)
        self.assertEqual(info.sfd.firmware_id, "b5c76f482e39e9d6a9115db5b8b7dc35")
        self.assertEqual(info.sfd.metadata.project_name, "Some project")
        self.assertEqual(info.sfd.metadata.author, "unit test")
        self.assertEqual(info.sfd.metadata.version, "1.2.3")
        self.assertIsNotNone(info.sfd.metadata.generation_info)
        self.assertEqual(info.sfd.metadata.generation_info.python_version, "3.10.5")
        self.assertEqual(info.sfd.metadata.generation_info.scrutiny_version, "0.0.1")
        self.assertEqual(info.sfd.metadata.generation_info.system_type, "Linux")
        self.assertEqual(info.sfd.metadata.generation_info.timestamp, datetime.fromtimestamp(1688431050))

        self.assertEqual(info.datalogging.state, DataloggerState.Standby)
        self.assertEqual(info.datalogging.completion_ratio, 0.56)

        self.assertIsNotNone(info.device_link)
        self.assertEqual(info.device_link.type, DeviceLinkType.UDP)
        self.assertIsInstance(info.device_link.config, UDPLinkConfig)
        assert isinstance(info.device_link.config, UDPLinkConfig)
        self.assertEqual(info.device_link.config.host, "localhost")
        self.assertEqual(info.device_link.config.port, 12345)
