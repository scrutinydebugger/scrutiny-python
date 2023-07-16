#    test_api_parser.py
#        Test suite for the parsing function used by the client
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2023 Scrutiny Debugger

import unittest

import scrutiny.sdk._api_parser as parser
from scrutiny.core.basic_types import *
from scrutiny.sdk.definitions import *
import scrutiny.server.api.typing as api_typing
import scrutiny.sdk.exceptions as sdk_exceptions
from copy import copy
from datetime import datetime
import logging
from test import ScrutinyUnitTest


class TestApiParser(ScrutinyUnitTest):
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

    def test_parse_inform_server_Status(self):
        def base() -> api_typing.S2C.InformServerStatus:
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

        self.assertEqual(len(info.device.forbidden_memory_regions), 2)
        self.assertEqual(info.device.forbidden_memory_regions[0].start, 0x1000)
        self.assertEqual(info.device.forbidden_memory_regions[0].end, 0x1FFF)
        self.assertEqual(info.device.forbidden_memory_regions[0].size, 0x1000)
        self.assertEqual(info.device.forbidden_memory_regions[1].start, 0x4000)
        self.assertEqual(info.device.forbidden_memory_regions[1].end, 0x4FFF)
        self.assertEqual(info.device.forbidden_memory_regions[1].size, 0x1000)
        self.assertEqual(len(info.device.readonly_memory_regions), 1)
        self.assertEqual(info.device.readonly_memory_regions[0].start, 0x8000)
        self.assertEqual(info.device.readonly_memory_regions[0].end, 0x8FFF)
        self.assertEqual(info.device.readonly_memory_regions[0].size, 0x1000)

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

        features = ['memory_write', 'datalogging', 'user_command', '_64bits']
        vals = [1, 'asd', None, [], {}]
        for feature in features:
            for val in vals:
                logging.debug(f"feature={feature}, val={val}")
                with self.assertRaises(sdk_exceptions.BadResponseError):
                    msg = base()
                    msg['device_info']['supported_feature_map'][feature] = val
                    parser.parse_inform_server_status(msg)

        for feature in features:
            logging.debug(f"feature={feature}")
            with self.assertRaises(sdk_exceptions.BadResponseError):
                msg = base()
                del msg['device_info']['supported_feature_map'][feature]
                parser.parse_inform_server_status(msg)

        ##
        msg = base()
        msg['device_status'] = "unknown"
        msg['loaded_sfd'] = None
        msg['device_info'] = None
        msg['device_session_id'] = None
        msg['device_comm_link']["link_type"] = 'none'
        msg['device_comm_link']["link_config"] = None
        info = parser.parse_inform_server_status(msg)

        self.assertIsNone(info.device)
        self.assertIsNone(info.sfd)
        self.assertIsNone(info.device_link.config)
        self.assertEqual(info.device_session_id, None)
        self.assertEqual(info.device_comm_state, DeviceCommState.NA)

        with self.assertRaises(sdk_exceptions.BadResponseError):
            msg = base()
            msg['device_status'] = "asd"
            parser.parse_inform_server_status(msg)

        with self.assertRaises(sdk_exceptions.BadResponseError):
            msg = base()
            msg["device_info"]['forbidden_memory_regions'][0]['end'] = msg["device_info"]['forbidden_memory_regions'][0]['start'] - 1
            info = parser.parse_inform_server_status(msg)

        with self.assertRaises(sdk_exceptions.BadResponseError):
            msg = base()
            msg["device_info"]['readonly_memory_regions'][0]['end'] = msg["device_info"]['readonly_memory_regions'][0]['start'] - 1
            info = parser.parse_inform_server_status(msg)

        fields = ['max_tx_data_size', 'max_rx_data_size', 'max_bitrate_bps', 'rx_timeout_us', 'heartbeat_timeout_us',
                  'address_size_bits', 'protocol_major', 'protocol_minor']
        for field in fields:
            vals = [None, 'asd', 1.5, [], {},]   # bad values
            for val in vals:
                logging.debug(f"field={field}, val={val}")
                with self.assertRaises(sdk_exceptions.BadResponseError):
                    msg = base()
                    msg["device_info"][field] = val
                    info = parser.parse_inform_server_status(msg)

        fields = ["project_name", "author", "version"]
        for field in fields:
            msg = base()
            msg['loaded_sfd']['metadata'][field] = None
            info = parser.parse_inform_server_status(msg)
            self.assertIsNone(getattr(info.sfd.metadata, field), f"field={field}")

            msg = base()
            msg['loaded_sfd']['metadata']["generation_info"] = None
            info = parser.parse_inform_server_status(msg)
            self.assertIsNone(info.sfd.metadata.generation_info.python_version)
            self.assertIsNone(info.sfd.metadata.generation_info.scrutiny_version)
            self.assertIsNone(info.sfd.metadata.generation_info.system_type)
            self.assertIsNone(info.sfd.metadata.generation_info.timestamp)

        msg = base()
        msg["device_datalogging_status"]["completion_ratio"] = None
        info = parser.parse_inform_server_status(msg)
        self.assertIsNone(info.datalogging.completion_ratio)

        with self.assertRaises(sdk_exceptions.BadResponseError):
            msg = base()
            msg["device_comm_link"]["link_type"] = 'serial'
            # We forgot to update the config.
            parser.parse_inform_server_status(msg)

        msg = base()
        msg["device_comm_link"]["link_type"] = 'serial'
        msg["device_comm_link"]["link_config"] = {
            "baudrate": 9600,
            "databits": 8,
            "parity": 'even',
            "portname": '/dev/ttyO1',
            'stopbits': '2'
        }
        # We forgot to update the config.
        info = parser.parse_inform_server_status(msg)

        self.assertEqual(info.device_link.type, DeviceLinkType.Serial)
        self.assertEqual(info.device_link.config.baudrate, 9600)
        self.assertEqual(info.device_link.config.databits, 8)
        self.assertEqual(info.device_link.config.parity, 'even')
        self.assertEqual(info.device_link.config.port, '/dev/ttyO1')
        self.assertEqual(info.device_link.config.stopbits, '2')

        serial_base = copy(msg)

        field_vals = {
            'baudrate': [None, 1.5, [], {}, 'asd'],
            'databits': [None, -1, 1.5, [], {}, 0, 'asd'],
            'parity': ['xx', 1, -1, None, [], {}],
            'portname': [1, None, [], {}],
            'stopbits': [None, -1, 1.5, [], {}, 0, 'asd']
        }

        for field, vals in field_vals.items():
            for val in vals:
                msg = copy(serial_base)
                logging.debug(f"field={field}, val={val}")
                with self.assertRaises(sdk_exceptions.BadResponseError):
                    msg["device_comm_link"]["link_config"][field] = val
                    parser.parse_inform_server_status(msg)

        for field in field_vals:
            msg = copy(serial_base)
            logging.debug(f"field={field}")
            with self.assertRaises(sdk_exceptions.BadResponseError):
                del msg["device_comm_link"]["link_config"][field]
                parser.parse_inform_server_status(msg)

        field_vals = {
            'host': [None, 1, 1.5, [], {}],
            'port': [None, 1.5, [], {}, 'asd']
        }

        for field, vals in field_vals.items():
            for val in vals:

                msg = base()
                logging.debug(f"field={field}, val={val}")
                with self.assertRaises(sdk_exceptions.BadResponseError):
                    msg["device_comm_link"]["link_config"][field] = val
                    parser.parse_inform_server_status(msg)

        for field in field_vals:
            msg = base()
            logging.debug(f"field={field}")
            with self.assertRaises(sdk_exceptions.BadResponseError):
                del msg["device_comm_link"]["link_config"][field]
                parser.parse_inform_server_status(msg)
