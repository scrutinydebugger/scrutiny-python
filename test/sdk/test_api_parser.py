#    test_api_parser.py
#        Test suite for the parsing function used by the client
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2023 Scrutiny Debugger

import unittest

from copy import copy
from datetime import datetime, timedelta
import logging
import time
from base64 import b64encode

import scrutiny.sdk._api_parser as parser
from scrutiny.core.basic_types import *
from scrutiny.sdk.definitions import *
import scrutiny.server.api.typing as api_typing
import scrutiny.sdk
import scrutiny.sdk.datalogging
sdk = scrutiny.sdk  # Workaround for vscode linter an submodule on alias

from test import ScrutinyUnitTest
from scrutiny.tools.typing import *


class TestApiParser(ScrutinyUnitTest):

    def test_parse_get_watchable_list(self):
        def base():
            return {
                "cmd": "response_get_watchable_list",
                "reqid": 123,
                "done": True,
                "qty": {"var": 2, "alias": 2, "rpv": 1},
                "content": {
                    "var": [{
                        "id": "id1",
                        "display_path": "/a/b/c",
                        "datatype": "sint32",
                        "enum": {
                            "name": "example_enum",
                            "values": {
                                "aaa": 1,
                                "bbb": 2,
                                "ccc": 3
                            }
                        }
                    }, {
                        "id": "id2",
                        "display_path": "/a/b/d",
                        "datatype": "uint64",
                    }],
                    "alias": [{
                        "id": "id3",
                        "display_path": "/x/y/z",
                        "datatype": "float32",
                    },
                        {
                        "id": "id4",
                        "display_path": "/x/y/w",
                        "datatype": "float64",
                    }],
                    "rpv": [{
                        "id": "id5",
                        "display_path": "/aaa/bbb/ccc",
                        "datatype": "sint8",
                    }]
                }
            }

        with self.assertRaises(Exception):
            m = base()
            m['cmd'] = 'asd'
            parser.parse_get_watchable_list(m)

        res = parser.parse_get_watchable_list(base())
        self.assertIsInstance(res, parser.GetWatchableListResponse)
        self.assertEqual(res.done, True)
        self.assertIsInstance(res.data, dict)
        self.assertEqual(len(res.data), 3)

        self.assertIn(WatchableType.Variable, res.data)
        self.assertIn(WatchableType.Alias, res.data)
        self.assertIn(WatchableType.RuntimePublishedValue, res.data)

        self.assertEqual(len(res.data[WatchableType.Variable]), 2)
        self.assertEqual(len(res.data[WatchableType.Alias]), 2)
        self.assertEqual(len(res.data[WatchableType.RuntimePublishedValue]), 1)

        self.assertIn("/a/b/c", res.data[WatchableType.Variable])
        self.assertIn("/a/b/d", res.data[WatchableType.Variable])
        self.assertIn("/x/y/z", res.data[WatchableType.Alias])
        self.assertIn("/x/y/w", res.data[WatchableType.Alias])
        self.assertIn("/aaa/bbb/ccc", res.data[WatchableType.RuntimePublishedValue])

        o = res.data[WatchableType.Variable]['/a/b/c']
        self.assertEqual(o.watchable_type, WatchableType.Variable)
        self.assertEqual(o.server_id, 'id1')
        self.assertEqual(o.datatype, EmbeddedDataType.sint32)
        self.assertEqual(o.enum.name, 'example_enum')
        self.assertEqual(o.enum.vals['aaa'], 1)
        self.assertEqual(o.enum.vals['bbb'], 2)
        self.assertEqual(o.enum.vals['ccc'], 3)
        self.assertEqual(len(o.enum.vals), 3)

        o = res.data[WatchableType.Variable]['/a/b/d']
        self.assertEqual(o.watchable_type, WatchableType.Variable)
        self.assertEqual(o.server_id, 'id2')
        self.assertEqual(o.datatype, EmbeddedDataType.uint64)

        o = res.data[WatchableType.Alias]['/x/y/z']
        self.assertEqual(o.watchable_type, WatchableType.Alias)
        self.assertEqual(o.server_id, 'id3')
        self.assertEqual(o.datatype, EmbeddedDataType.float32)

        o = res.data[WatchableType.Alias]['/x/y/w']
        self.assertEqual(o.watchable_type, WatchableType.Alias)
        self.assertEqual(o.server_id, 'id4')
        self.assertEqual(o.datatype, EmbeddedDataType.float64)

        o = res.data[WatchableType.RuntimePublishedValue]['/aaa/bbb/ccc']
        self.assertEqual(o.watchable_type, WatchableType.RuntimePublishedValue)
        self.assertEqual(o.server_id, 'id5')
        self.assertEqual(o.datatype, EmbeddedDataType.sint8)

        for wt in ('var', 'alias', 'rpv'):
            with self.assertRaises(sdk.exceptions.BadResponseError):
                response = base()
                response['qty'][wt] = 5
                res = parser.parse_get_watchable_list(response)

        class Delete:
            pass

        for wt in ('var', 'alias', 'rpv'):
            for val in [[], {}, None, 3.5, 1, True, Delete, ""]:
                for field in ("id", 'datatype', 'display_path'):
                    with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"wt={wt}, val={val}, field={field}"):
                        response = base()
                        if val == Delete:
                            del response['content'][wt][0][field]
                        else:
                            response['content'][wt][0][field] = val
                        parser.parse_get_watchable_list(response)

        for val in [[], {}, None, 3.5, 1, True, Delete, ""]:
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                response = base()
                if val == Delete:
                    del response["content"]['var'][0]['enum']['name']
                else:
                    response["content"]['var'][0]['enum']['name'] = val

                parser.parse_get_watchable_list(response)

        for val in [[], None, 3.5, 1, True, Delete, "", "aaa"]:
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                response = base()
                if val == Delete:
                    del response["content"]['var'][0]['enum']['values']
                else:
                    response["content"]['var'][0]['enum']['values'] = val

                parser.parse_get_watchable_list(response)

        for val in [[], None, 3.5, 1, True, Delete, "", "aaa"]:
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                response = base()
                if val == Delete:
                    del response["content"]['var'][0]['enum']['values']
                else:
                    response["content"]['var'][0]['enum']['values'] = val

                parser.parse_get_watchable_list(response)

        for val in [None, 3.5, 1, True, ""]:
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                response = base()
                response["content"]['var'][0]['enum']['values'][val] = 123
                parser.parse_get_watchable_list(response)

        for val in [{}, [], None, 3.5, True, "", "aaa"]:
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                response = base()
                response["content"]['var'][0]['enum']['values']["aaa"] = val
                parser.parse_get_watchable_list(response)

    def test_parse_subscribe_watchable(self):
        def base():
            return {
                "cmd": "response_subscribe_watchable",
                "reqid": 123,
                "subscribed": {
                    '/a/b/c': {
                        'id': 'abc',
                        'type': 'var',
                        'datatype': 'float32'
                    },
                    '/a/b/d': {
                        'id': 'abd',
                        'type': 'alias',
                        'datatype': 'sint8',
                        'enum': {
                            'name': 'the_enum',
                            'values': {
                                'a': 1,
                                'b': 2,
                                'c': 3,
                            }
                        }
                    }
                }
            }

        with self.assertRaises(Exception):
            m = base()
            m['cmd'] = 'asd'
            parser.parse_subscribe_watchable_response(m)

        response = base()
        res = parser.parse_subscribe_watchable_response(response)
        self.assertIsInstance(res, dict)
        self.assertIn('/a/b/c', res)
        self.assertIn('/a/b/d', res)

        self.assertEqual(res['/a/b/c'].server_id, 'abc')
        self.assertEqual(res['/a/b/c'].datatype, EmbeddedDataType.float32)
        self.assertEqual(res['/a/b/c'].watchable_type, sdk.WatchableType.Variable)
        self.assertIsNone(res['/a/b/c'].enum)

        self.assertEqual(res['/a/b/d'].server_id, 'abd')
        self.assertEqual(res['/a/b/d'].datatype, EmbeddedDataType.sint8)
        self.assertEqual(res['/a/b/d'].watchable_type, sdk.WatchableType.Alias)
        self.assertIsNotNone(res['/a/b/d'].enum)
        self.assertEqual(res['/a/b/d'].enum.name, 'the_enum')
        self.assertEqual(res['/a/b/d'].enum.get_value('a'), 1)
        self.assertEqual(res['/a/b/d'].enum.get_value('b'), 2)
        self.assertEqual(res['/a/b/d'].enum.get_value('c'), 3)

        class Delete:
            pass
        delete = Delete()
        for val in [1, True, [], None, "asd", delete]:
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f'val={val}'):
                msg = base()
                if val is delete:
                    del msg['subscribed']
                else:
                    msg['subscribed'] = val
                parser.parse_subscribe_watchable_response(msg)

        for val in [1, True, [], None, "asd", delete]:
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f'val={val}'):
                msg = base()
                if val is delete:
                    del msg['subscribed']['/a/b/c']['datatype']
                else:
                    msg['subscribed']['/a/b/c']['datatype'] = val
                parser.parse_subscribe_watchable_response(msg)

        for val in [1, True, [], None, {}, delete]:
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f'val={val}'):
                msg = base()
                if val is delete:
                    del msg['subscribed']['/a/b/c']['id']
                else:
                    msg['subscribed']['/a/b/c']['id'] = val
                parser.parse_subscribe_watchable_response(msg)

        for val in [1, True, [], None, {}, delete, "asd"]:
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f'val={val}'):
                msg = base()
                if val is delete:
                    del msg['subscribed']['/a/b/c']['type']
                else:
                    msg['subscribed']['/a/b/c']['type'] = val
                parser.parse_subscribe_watchable_response(msg)

    def test_get_device_info(self):
        def base() -> api_typing.S2C.GetDeviceInfo:
            return {
                'cmd': "response_get_device_info",
                "available": True,
                "device_info": {
                    "session_id": "5b8b7dc35b5c766a9115dbf482e39e9d",
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
                    "readonly_memory_regions": [{'start': 0x8000, 'end': 0x8FFF}],
                    "datalogging_capabilities": {
                        "buffer_size": 4096,
                        "encoding": 'raw',
                        "max_nb_signal": 32,
                        "sampling_rates": [
                            {
                                "identifier": 0,
                                "name": "loop0",
                                "frequency": 1000,
                                "type": "fixed_freq"
                            },
                            {
                                "identifier": 1,
                                "name": "loop1",
                                "frequency": None,
                                "type": "variable_freq"
                            }
                        ]
                    }
                }
            }

        with self.assertRaises(Exception):
            m = base()
            m['cmd'] = 'asd'
            parser.parse_get_device_info(m)

        msg = base()
        device_info = parser.parse_get_device_info(msg)

        self.assertIsNotNone(device_info)
        self.assertEqual(device_info.device_id, "b5c76f482e39e9d6a9115db5b8b7dc35")
        self.assertEqual(device_info.display_name, "TestApp Executable")
        self.assertEqual(device_info.max_tx_data_size, 256)
        self.assertEqual(device_info.max_rx_data_size, 128)
        self.assertEqual(device_info.max_bitrate_bps, 100000)
        self.assertEqual(device_info.rx_timeout_us, 50000)
        self.assertEqual(device_info.heartbeat_timeout, 5)
        self.assertEqual(device_info.address_size_bits, 64)
        self.assertEqual(device_info.protocol_major, 1)
        self.assertEqual(device_info.protocol_minor, 0)
        self.assertEqual(device_info.supported_features.memory_write, True)
        self.assertEqual(device_info.supported_features.datalogging, True)
        self.assertEqual(device_info.supported_features.user_command, False)
        self.assertEqual(device_info.supported_features.sixtyfour_bits, True)

        self.assertEqual(len(device_info.forbidden_memory_regions), 2)
        self.assertEqual(device_info.forbidden_memory_regions[0].start, 0x1000)
        self.assertEqual(device_info.forbidden_memory_regions[0].end, 0x1FFF)
        self.assertEqual(device_info.forbidden_memory_regions[0].size, 0x1000)
        self.assertEqual(device_info.forbidden_memory_regions[1].start, 0x4000)
        self.assertEqual(device_info.forbidden_memory_regions[1].end, 0x4FFF)
        self.assertEqual(device_info.forbidden_memory_regions[1].size, 0x1000)
        self.assertEqual(len(device_info.readonly_memory_regions), 1)
        self.assertEqual(device_info.readonly_memory_regions[0].start, 0x8000)
        self.assertEqual(device_info.readonly_memory_regions[0].end, 0x8FFF)
        self.assertEqual(device_info.readonly_memory_regions[0].size, 0x1000)

        features = ['memory_write', 'datalogging', 'user_command', '_64bits']
        vals = [1, 'asd', None, [], {}]
        for feature in features:
            for val in vals:
                logging.debug(f"feature={feature}, val={val}")
                with self.assertRaises(sdk.exceptions.BadResponseError):
                    msg = base()
                    msg['device_info']['supported_feature_map'][feature] = val
                    parser.parse_get_device_info(msg)

        for feature in features:
            logging.debug(f"feature={feature}")
            with self.assertRaises(sdk.exceptions.BadResponseError):
                msg = base()
                del msg['device_info']['supported_feature_map'][feature]
                parser.parse_get_device_info(msg)

        capabilities = device_info.datalogging_capabilities

        self.assertIsNotNone(capabilities)
        self.assertEqual(capabilities.buffer_size, 4096)
        self.assertEqual(capabilities.encoding, sdk.datalogging.DataloggingEncoding.RAW)
        self.assertEqual(capabilities.max_nb_signal, 32)
        self.assertEqual(len(capabilities.sampling_rates), 2)

        self.assertIsInstance(capabilities.sampling_rates[0], sdk.datalogging.FixedFreqSamplingRate)
        assert isinstance(capabilities.sampling_rates[0], sdk.datalogging.FixedFreqSamplingRate)
        self.assertEqual(capabilities.sampling_rates[0].name, "loop0")
        self.assertEqual(capabilities.sampling_rates[0].identifier, 0)
        self.assertEqual(capabilities.sampling_rates[0].frequency, 1000.0)

        self.assertIsInstance(capabilities.sampling_rates[1], sdk.datalogging.VariableFreqSamplingRate)
        self.assertEqual(capabilities.sampling_rates[1].name, "loop1")
        self.assertEqual(capabilities.sampling_rates[1].identifier, 1)

        ###
        msg = base()
        msg['device_info']['datalogging_capabilities'] = None
        device_info = parser.parse_get_device_info(msg)
        self.assertIsNone(device_info.datalogging_capabilities)

        with self.assertRaises(sdk.exceptions.BadResponseError):
            msg = base()
            msg["device_info"]['forbidden_memory_regions'][0]['end'] = msg["device_info"]['forbidden_memory_regions'][0]['start'] - 1
            parser.parse_get_device_info(msg)

        with self.assertRaises(sdk.exceptions.BadResponseError):
            msg = base()
            msg["device_info"]['readonly_memory_regions'][0]['end'] = msg["device_info"]['readonly_memory_regions'][0]['start'] - 1
            parser.parse_get_device_info(msg)

        with self.assertRaises(sdk.exceptions.BadResponseError):
            msg = base()
            msg["device_info"]['datalogging_capabilities'] = 'asdasdasd'
            parser.parse_get_device_info(msg)

        fields = ['max_tx_data_size', 'max_rx_data_size', 'max_bitrate_bps', 'rx_timeout_us', 'heartbeat_timeout_us',
                  'address_size_bits', 'protocol_major', 'protocol_minor']
        for field in fields:
            vals = ['asd', 1.5, [], {},]   # bad values
            for val in vals:
                logging.debug(f"field={field}, val={val}")
                with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"field={field}, val={val}"):
                    msg = base()
                    msg["device_info"][field] = val
                    info = parser.parse_get_device_info(msg)

        msg = base()
        msg["device_info"]["max_bitrate_bps"] = None
        info = parser.parse_get_device_info(msg)

    def test_parse_inform_server_status(self):
        def base() -> api_typing.S2C.InformServerStatus:
            return {
                "cmd": "inform_server_status",
                "reqid": 2,
                "device_status": "connected_ready",
                "device_session_id": "3d41973c65ba42218ab65c829a8c385e",
                "loaded_sfd_firmware_id": "b5c76f482e39e9d6a9115db5b8b7dc35",
                "device_datalogging_status": {
                    "datalogger_state": "standby",
                    "completion_ratio": 0.56
                },
                "device_comm_link": {
                    "link_type": "udp",
                    "link_operational": True,
                    "link_config": {
                        "host": "localhost",
                        "port": 12345
                    }
                }
            }

        with self.assertRaises(Exception):
            m = base()
            m['cmd'] = 'asd'
            parser.parse_inform_server_status(m)

        msg = base()
        info = parser.parse_inform_server_status(msg)

        self.assertEqual(info.device_comm_state, DeviceCommState.ConnectedReady)
        self.assertEqual(info.device_session_id, "3d41973c65ba42218ab65c829a8c385e")

        self.assertIsNotNone(info.sfd_firmware_id)
        self.assertEqual(info.sfd_firmware_id, "b5c76f482e39e9d6a9115db5b8b7dc35")

        self.assertEqual(info.datalogging.state, DataloggerState.Standby)
        self.assertEqual(info.datalogging.completion_ratio, 0.56)

        self.assertIsNotNone(info.device_link)
        self.assertEqual(info.device_link.type, DeviceLinkType.UDP)
        self.assertIsInstance(info.device_link.config, UDPLinkConfig)
        assert isinstance(info.device_link.config, UDPLinkConfig)
        self.assertEqual(info.device_link.config.host, "localhost")
        self.assertEqual(info.device_link.config.port, 12345)

        ##

        msg = base()
        msg['device_status'] = "unknown"
        msg['loaded_sfd_firmware_id'] = None
        msg['device_session_id'] = None
        msg['device_comm_link']["link_type"] = 'none'
        msg['device_comm_link']["link_config"] = None
        info = parser.parse_inform_server_status(msg)

        self.assertIsNone(info.sfd_firmware_id)
        self.assertIsInstance(info.device_link.config, sdk.NoneLinkConfig)
        self.assertEqual(info.device_session_id, None)
        self.assertEqual(info.device_comm_state, DeviceCommState.NA)

        msg = base()
        msg["device_datalogging_status"]["completion_ratio"] = None
        info = parser.parse_inform_server_status(msg)
        self.assertIsNone(info.datalogging.completion_ratio)

        msg = base()
        with self.assertRaises(sdk.exceptions.BadResponseError):
            msg = base()
            msg['device_status'] = "asd"
            parser.parse_inform_server_status(msg)

        with self.assertRaises(sdk.exceptions.BadResponseError):
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
            'stopbits': '2',
            'start_delay': 0.2
        }
        # We forgot to update the config.
        info = parser.parse_inform_server_status(msg)

        self.assertEqual(info.device_link.type, DeviceLinkType.Serial)
        self.assertEqual(info.device_link.config.baudrate, 9600)
        self.assertEqual(info.device_link.config.databits, sdk.SerialLinkConfig.DataBits.EIGHT)
        self.assertEqual(info.device_link.config.parity, sdk.SerialLinkConfig.Parity.EVEN)
        self.assertEqual(info.device_link.config.port, '/dev/ttyO1')
        self.assertEqual(info.device_link.config.stopbits, sdk.SerialLinkConfig.StopBits.TWO)
        self.assertEqual(info.device_link.config.start_delay, 0.2)

        serial_base = copy(msg)

        field_vals = {
            'baudrate': [None, 1.5, [], {}, 'asd'],
            'databits': [None, -1, 1.5, [], {}, 0, 'asd'],
            'parity': ['xx', 1, -1, None, [], {}],
            'portname': [1, None, [], {}],
            'stopbits': [None, -1, 1.5, [], {}, 0, 'asd'],
            'start_delay': [None, -1, [], {}, 'asd']
        }

        for field, vals in field_vals.items():
            for val in vals:
                msg = copy(serial_base)
                logging.debug(f"field={field}, val={val}")
                with self.assertRaises(sdk.exceptions.BadResponseError):
                    msg["device_comm_link"]["link_config"][field] = val
                    parser.parse_inform_server_status(msg)

        for field in field_vals:
            msg = copy(serial_base)
            logging.debug(f"field={field}")
            with self.assertRaises(sdk.exceptions.BadResponseError):
                del msg["device_comm_link"]["link_config"][field]
                parser.parse_inform_server_status(msg)

        # Test RTT Link
        msg = base()
        msg["device_comm_link"]["link_type"] = 'rtt'
        msg["device_comm_link"]["link_config"] = {
            "jlink_interface": "icsp",
            "target_device": "some_device"
        }
        info = parser.parse_inform_server_status(msg)
        self.assertEqual(info.device_link.type, DeviceLinkType.RTT)
        assert isinstance(info.device_link.config, sdk.RTTLinkConfig)
        self.assertEqual(info.device_link.config.jlink_interface, sdk.RTTLinkConfig.JLinkInterface.ICSP)
        self.assertEqual(info.device_link.config.target_device, "some_device")

        for val in ["jtag", "swd", "fine", "icsp", "spi", "c2"]:
            msg = base()
            msg["device_comm_link"]["link_type"] = 'rtt'
            msg["device_comm_link"]["link_config"] = {
                "jlink_interface": val,
                "target_device": "some_device"
            }
            parser.parse_inform_server_status(msg)  # no error

        with self.assertRaises(sdk.exceptions.BadResponseError):
            msg = base()
            msg["device_comm_link"]["link_type"] = 'rtt'
            msg["device_comm_link"]["link_config"] = {
                "jlink_interface": "notvalid",  # Cause a failure
                "target_device": "some_device"
            }
            parser.parse_inform_server_status(msg)

        class Delete:
            pass

        for field in ['jlink_interface', 'target_device']:
            for val in [1, None, 1.5, True, [], Delete()]:
                msg = base()
                msg["device_comm_link"]["link_type"] = 'rtt'
                msg["device_comm_link"]["link_config"] = {
                    "jlink_interface": "jtag",
                    "target_device": "some_device"
                }

                if isinstance(val, Delete):
                    del msg["device_comm_link"]['link_config'][field]
                else:
                    msg["device_comm_link"]['link_config'][field] = val

                with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"field={field}. val={val}"):
                    parser.parse_inform_server_status(msg)

        # Test bad UDP vals
        field_vals = {
            'host': [None, 1, 1.5, [], {}],
            'port': [None, 1.5, [], {}, 'asd']
        }

        for field, vals in field_vals.items():
            for val in vals:
                msg = base()
                logging.debug(f"field={field}, val={val}")
                with self.assertRaises(sdk.exceptions.BadResponseError):
                    msg["device_comm_link"]["link_config"][field] = val
                    parser.parse_inform_server_status(msg)

        for field in field_vals:
            msg = base()
            logging.debug(f"field={field}")
            with self.assertRaises(sdk.exceptions.BadResponseError):
                del msg["device_comm_link"]["link_config"][field]
                parser.parse_inform_server_status(msg)

    def test_parse_read_datalogging_acquisition_content(self):
        now = datetime.now()

        def base() -> api_typing.S2C.ReadDataloggingAcquisitionContent:
            return {
                "cmd": "response_read_datalogging_acquisition_content",
                "reqid": None,
                "firmware_id": "foo",
                "firmware_name": "hello",
                "name": "acquisition 123",
                "reference_id": "bar.baz",
                "trigger_index": 5,
                "timestamp": now.timestamp(),
                "xdata": {
                    "name": "Xaxis",
                    "watchable": {
                        'path': "path/to/xaxis/item",
                        'type': "var"
                    },
                    "data": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
                },
                "yaxes": [
                    {"id": 0, "name": "Y-Axis1"},
                    {"id": 1, "name": "Y-Axis2"},
                ],
                "signals": [
                    {
                        "axis_id": 0,
                        "name": "signal1",
                        "watchable": {
                            'path': "/path/to/signal1",
                            'type': 'var'
                        },
                        "data": [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
                    },
                    {
                        "axis_id": 0,
                        "name": "signal2",
                        "watchable": {
                            'path': "/path/to/signal2",
                            'type': 'alias'
                        },
                        "data": [0, -10, -20, -30, -40, -50, -60, -70, -80, -90]
                    },
                    {
                        "axis_id": 1,
                        "name": "signal3",
                        "watchable": {
                            'path': "/path/to/signal3",
                            'type': 'rpv'
                        },
                        "data": [-4.5, -3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5, 4.5]
                    }
                ]
            }

        with self.assertRaises(Exception):
            m = base()
            m['cmd'] = 'asd'
            parser.parse_read_datalogging_acquisition_content_response(m)

        msg = base()
        acq = parser.parse_read_datalogging_acquisition_content_response(msg)

        self.assertIsInstance(acq, sdk.datalogging.DataloggingAcquisition)
        self.assertEqual(acq.firmware_id, "foo")
        self.assertEqual(acq.firmware_name, 'hello')
        self.assertEqual(acq.name, "acquisition 123")
        self.assertEqual(acq.reference_id, "bar.baz")
        self.assertLessEqual(abs(acq.acq_time - now), timedelta(seconds=1))

        self.assertEqual(acq.xdata.name, "Xaxis")
        self.assertEqual(acq.xdata.logged_watchable.path, "path/to/xaxis/item")
        self.assertEqual(acq.xdata.logged_watchable.type, WatchableType.Variable)
        self.assertEqual(acq.xdata.get_data(), [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0])

        yaxes = acq.get_unique_yaxis_list()
        self.assertEqual(len(yaxes), 2)
        yaxes.sort(key=lambda x: x.axis_id)
        self.assertEqual(yaxes[0].axis_id, 0)
        self.assertEqual(yaxes[0].name, "Y-Axis1")
        self.assertEqual(yaxes[1].axis_id, 1)
        self.assertEqual(yaxes[1].name, "Y-Axis2")
        yaxes_map: Dict[int, sdk.datalogging.AxisDefinition] = {}
        for yaxis in yaxes:
            yaxes_map[yaxis.axis_id] = yaxis

        data = acq.get_data()
        self.assertEqual(len(data), 3)
        data.sort(key=lambda x: x.series.name)

        self.assertIn(data[0].axis.axis_id, yaxes_map)
        self.assertEqual(yaxes_map[data[0].axis.axis_id].name, "Y-Axis1")
        self.assertEqual(data[0].series.name, "signal1")
        self.assertEqual(data[0].series.logged_watchable.path, "/path/to/signal1")
        self.assertEqual(data[0].series.logged_watchable.type, WatchableType.Variable)

        self.assertIn(data[1].axis.axis_id, yaxes_map)
        self.assertEqual(yaxes_map[data[1].axis.axis_id].name, "Y-Axis1")
        self.assertEqual(data[1].series.name, "signal2")
        self.assertEqual(data[1].series.logged_watchable.path, "/path/to/signal2")
        self.assertEqual(data[1].series.logged_watchable.type, WatchableType.Alias)

        self.assertIn(data[2].axis.axis_id, yaxes_map)
        self.assertEqual(yaxes_map[data[2].axis.axis_id].name, "Y-Axis2")
        self.assertEqual(data[2].series.name, "signal3")
        self.assertEqual(data[2].series.logged_watchable.path, "/path/to/signal3")
        self.assertEqual(data[2].series.logged_watchable.type, WatchableType.RuntimePublishedValue)

        for field in ['firmware_id', 'firmware_name', 'name', 'reference_id', 'trigger_index', 'timestamp', 'xdata', 'yaxes', 'signals']:
            msg = base()
            del msg[field]
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"Field : {field}"):
                parser.parse_read_datalogging_acquisition_content_response(msg)

        for field in ['name', 'watchable', 'data']:
            msg = base()
            del msg['xdata'][field]
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"Field : {field}"):
                parser.parse_read_datalogging_acquisition_content_response(msg)

        msg = base()
        msg['xdata']['watchable'] = None
        response = parser.parse_read_datalogging_acquisition_content_response(msg)
        self.assertIsNone(response.xdata.logged_watchable)

        for field in ['axis_id', 'name', 'watchable', 'data']:
            msg = base()
            for i in range(len(msg['signals'])):
                del msg['signals'][i][field]
                with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"Field : {field}"):
                    parser.parse_read_datalogging_acquisition_content_response(msg)

        for val in [10000, -1, "asd", 1.1, {}, []]:
            msg = base()
            msg['trigger_index'] = val
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                parser.parse_read_datalogging_acquisition_content_response(msg)

        for i in range(3):
            for val in [3, -1, "asd", 1.1, None, {}, []]:
                msg = base()
                msg['signals'][i]["axis_id"] = val
                with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                    parser.parse_read_datalogging_acquisition_content_response(msg)

            for val in [3, []]:
                msg = base()
                msg['signals'][i]["watchable"] = val
                with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                    parser.parse_read_datalogging_acquisition_content_response(msg)

            for val in [None, 3, {}, True]:
                msg = base()
                msg['signals'][i]["watchable"]['path'] = val
                with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                    parser.parse_read_datalogging_acquisition_content_response(msg)

            for val in [None, 3, {}, True, 'asdasdasd']:
                msg = base()
                msg['signals'][i]["watchable"]['type'] = val
                with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                    parser.parse_read_datalogging_acquisition_content_response(msg)

            msg = base()
            msg['signals'][i]["watchable"] = None   # Not allowed for Y data
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                parser.parse_read_datalogging_acquisition_content_response(msg)

            for val in [3, None, {}, []]:
                msg = base()
                msg['signals'][i]["name"] = val
                with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                    parser.parse_read_datalogging_acquisition_content_response(msg)

            for val in [3, None, "asd", {}]:
                msg = base()
                msg['signals'][i]["data"] = val
                with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                    parser.parse_read_datalogging_acquisition_content_response(msg)

            for val in [None, "asd", {}]:
                msg = base()
                msg['signals'][i]["data"][0] = val
                with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                    parser.parse_read_datalogging_acquisition_content_response(msg)

        for i in range(2):
            for val in [None, "asd", {}, [], 1.1]:
                msg = base()
                msg['yaxes'][i]['id'] = val
                with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                    parser.parse_read_datalogging_acquisition_content_response(msg)

            for val in [None, 1, {}, [], 1.1]:
                msg = base()
                msg['yaxes'][i]['name'] = val
                with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                    parser.parse_read_datalogging_acquisition_content_response(msg)

    def test_parse_list_datalogging_acquisition_response(self):
        now = datetime.now()

        def base() -> api_typing.S2C.ListDataloggingAcquisition:
            return {
                "cmd": "response_list_datalogging_acquisitions",
                "reqid": None,
                "total": 5,
                "acquisitions": [
                    {
                        'firmware_id': "firmware 1",
                        'name': "hello",
                        'timestamp': now.timestamp(),
                        'reference_id': "refid1",
                        'firmware_metadata': {
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
                    {
                        'firmware_id': "firmware 2",
                        'name': "hello2",
                        'timestamp': now.timestamp() + 5,
                        'reference_id': "refid2",
                        'firmware_metadata': {
                            "project_name": "Some project 2",
                            "author": "unit test 2",
                            "version": "1.2.4",
                            "generation_info": {
                                "time": 1688431050,
                                "python_version": "3.10.6",
                                "scrutiny_version": "0.0.2",
                                "system_type": "Windows"
                            }
                        }
                    }
                ]
            }

        with self.assertRaises(Exception):
            m = base()
            m['cmd'] = 'asd'
            parser.parse_list_datalogging_acquisitions_response(m)

        msg = base()
        acquisitions = parser.parse_list_datalogging_acquisitions_response(msg)

        self.assertIsInstance(acquisitions, list)
        self.assertEqual(len(acquisitions), 2)

        self.assertEqual(acquisitions[0].firmware_id, "firmware 1")
        self.assertEqual(acquisitions[0].name, "hello")
        self.assertLess(abs(acquisitions[0].timestamp - now), timedelta(seconds=1))
        self.assertEqual(acquisitions[0].reference_id, "refid1")
        self.assertEqual(acquisitions[0].firmware_metadata.project_name, "Some project")
        self.assertEqual(acquisitions[0].firmware_metadata.version, "1.2.3")
        self.assertEqual(acquisitions[0].firmware_metadata.author, "unit test")
        self.assertEqual(acquisitions[0].firmware_metadata.generation_info.timestamp, datetime.fromtimestamp(1688431050))
        self.assertEqual(acquisitions[0].firmware_metadata.generation_info.python_version, "3.10.5")
        self.assertEqual(acquisitions[0].firmware_metadata.generation_info.scrutiny_version, "0.0.1")
        self.assertEqual(acquisitions[0].firmware_metadata.generation_info.system_type, "Linux")

        self.assertEqual(acquisitions[1].firmware_id, "firmware 2")
        self.assertEqual(acquisitions[1].name, "hello2")
        self.assertLess(abs(acquisitions[1].timestamp - (now + timedelta(seconds=5))), timedelta(seconds=1))
        self.assertEqual(acquisitions[1].reference_id, "refid2")
        self.assertEqual(acquisitions[1].firmware_metadata.project_name, "Some project 2")
        self.assertEqual(acquisitions[1].firmware_metadata.version, "1.2.4")
        self.assertEqual(acquisitions[1].firmware_metadata.author, "unit test 2")
        self.assertEqual(acquisitions[1].firmware_metadata.generation_info.timestamp, datetime.fromtimestamp(1688431050))
        self.assertEqual(acquisitions[1].firmware_metadata.generation_info.python_version, "3.10.6")
        self.assertEqual(acquisitions[1].firmware_metadata.generation_info.scrutiny_version, "0.0.2")
        self.assertEqual(acquisitions[1].firmware_metadata.generation_info.system_type, "Windows")

        msg = base()
        msg["acquisitions"][0]["firmware_metadata"] = None
        acquisitions = parser.parse_list_datalogging_acquisitions_response(msg)
        self.assertIsNone(acquisitions[0].firmware_metadata)

        for field in ['author', 'project_name', 'version', 'generation_info']:
            msg = base()
            msg["acquisitions"][0]["firmware_metadata"][field] = None
            acquisitions = parser.parse_list_datalogging_acquisitions_response(msg)
            if field != 'generation_info':
                self.assertIsNone(getattr(acquisitions[0].firmware_metadata, field))
            else:
                attr = cast(sdk.SFDGenerationInfo, getattr(acquisitions[0].firmware_metadata, field))
                self.assertIsInstance(attr, sdk.SFDGenerationInfo)
                self.assertIsNone(attr.python_version)
                self.assertIsNone(attr.scrutiny_version)
                self.assertIsNone(attr.system_type)
                self.assertIsNone(attr.timestamp)

            msg = base()
            del msg["acquisitions"][0]["firmware_metadata"][field]
            acquisitions = parser.parse_list_datalogging_acquisitions_response(msg)
            if field != 'generation_info':
                self.assertIsNone(getattr(acquisitions[0].firmware_metadata, field))
            else:
                attr = cast(sdk.SFDGenerationInfo, getattr(acquisitions[0].firmware_metadata, field))
                self.assertIsInstance(attr, sdk.SFDGenerationInfo)
                self.assertIsNone(attr.python_version)
                self.assertIsNone(attr.scrutiny_version)
                self.assertIsNone(attr.system_type)
                self.assertIsNone(attr.timestamp)

        class Delete:
            pass
        delete = Delete()

        for val in [None, 1, [], {}, True, delete]:
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                msg = base()
                if val is delete:
                    del msg["acquisitions"][0]["firmware_id"]
                else:
                    msg["acquisitions"][0]["firmware_id"] = val
                parser.parse_list_datalogging_acquisitions_response(msg)

        for val in [None, 1, [], {}, True, delete]:
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                msg = base()
                if val is delete:
                    del msg["acquisitions"][0]["name"]
                else:
                    msg["acquisitions"][0]["name"] = val
                parser.parse_list_datalogging_acquisitions_response(msg)

        for val in [None, 1, [], {}, True, delete]:
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                msg = base()
                if val is delete:
                    del msg["acquisitions"][0]["reference_id"]
                else:
                    msg["acquisitions"][0]["reference_id"] = val
                parser.parse_list_datalogging_acquisitions_response(msg)

        for val in [None, "asd", [], {}, True, delete]:
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                msg = base()
                if val is delete:
                    del msg["acquisitions"][0]["timestamp"]
                else:
                    msg["acquisitions"][0]["timestamp"] = val
                parser.parse_list_datalogging_acquisitions_response(msg)

        for val in ["asd", [], 1, True, delete]:
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                msg = base()
                if val is delete:
                    del msg["acquisitions"][0]["firmware_metadata"]
                else:
                    msg["acquisitions"][0]["firmware_metadata"] = val
                parser.parse_list_datalogging_acquisitions_response(msg)

        for val in [[], 1, True, {}]:
            msg = base()
            msg["acquisitions"][0]["firmware_metadata"]["author"] = val
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                parser.parse_list_datalogging_acquisitions_response(msg)

        for val in [[], 1, True, {}]:
            msg = base()
            msg["acquisitions"][0]["firmware_metadata"]["project_name"] = val
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                parser.parse_list_datalogging_acquisitions_response(msg)

        for val in [[], 1, True, {}]:
            msg = base()
            msg["acquisitions"][0]["firmware_metadata"]["version"] = val
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                parser.parse_list_datalogging_acquisitions_response(msg)

        for val in [[], 1, True, {}]:
            msg = base()
            msg["acquisitions"][0]["firmware_metadata"]["generation_info"]["python_version"] = val
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                parser.parse_list_datalogging_acquisitions_response(msg)

        for val in [[], 1, True, {}]:
            msg = base()
            msg["acquisitions"][0]["firmware_metadata"]["generation_info"]["scrutiny_version"] = val
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                parser.parse_list_datalogging_acquisitions_response(msg)

        for val in [[], 1, True, {}]:
            msg = base()
            msg["acquisitions"][0]["firmware_metadata"]["generation_info"]["system_type"] = val
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                parser.parse_list_datalogging_acquisitions_response(msg)

        for val in ["asd", [], True, {}]:
            msg = base()
            msg["acquisitions"][0]["firmware_metadata"]["generation_info"]["time"] = val
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"val={val}"):
                parser.parse_list_datalogging_acquisitions_response(msg)

    def test_parse_get_watchable_count(self):
        def base():
            return {
                "cmd": "response_get_watchable_count",
                "reqid": None,
                'qty': {
                    'alias': 10,
                    'var': 20,
                    'rpv': 30,
                }
            }

        with self.assertRaises(Exception):
            m = base()
            m['cmd'] = 'asd'
            parser.parse_get_watchable_count(m)

        msg = base()
        count = parser.parse_get_watchable_count(msg)
        self.assertEqual(count[WatchableType.Alias], 10)
        self.assertEqual(count[WatchableType.Variable], 20)
        self.assertEqual(count[WatchableType.RuntimePublishedValue], 30)
        self.assertEqual(len(count), 3)

        with self.assertRaises(sdk.exceptions.BadResponseError):
            msg = base()
            del msg['qty']
            parser.parse_get_watchable_count(msg)

        class Delete:
            pass

        for key in ['var', 'alias', 'rpv']:
            for val in [None, -1, 2.5, [], {}, True, Delete]:
                with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"key={key}, val={val}"):
                    msg = base()
                    if val == Delete:
                        del msg['qty'][key]
                    else:
                        msg['qty'][key] = val
                    parser.parse_get_watchable_count(msg)

    def test_parse_get_loaded_sfd(self):
        def base():
            return {
                "cmd": "response_get_loaded_sfd",
                "reqid": None,
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
            }

        with self.assertRaises(Exception):
            m = base()
            m['cmd'] = 'asd'
            parser.parse_get_loaded_sfd(m)

        msg = base()
        sfd = parser.parse_get_loaded_sfd(msg)

        self.assertIsNotNone(sfd)
        self.assertEqual(sfd.metadata.project_name, "Some project")
        self.assertEqual(sfd.metadata.author, "unit test")
        self.assertEqual(sfd.metadata.version, "1.2.3")
        self.assertIsNotNone(sfd.metadata.generation_info)
        self.assertEqual(sfd.metadata.generation_info.python_version, "3.10.5")
        self.assertEqual(sfd.metadata.generation_info.scrutiny_version, "0.0.1")
        self.assertEqual(sfd.metadata.generation_info.system_type, "Linux")
        self.assertEqual(sfd.metadata.generation_info.timestamp, datetime.fromtimestamp(1688431050))

        msg = base()
        msg['firmware_id'] = None
        msg['metadata'] = None
        sfd = parser.parse_get_loaded_sfd(msg)
        self.assertIsNone(sfd)

        # Negative checks
        fields = ["project_name", "author", "version"]
        for field in fields:
            msg = base()
            msg['metadata'][field] = None
            sfd = parser.parse_get_loaded_sfd(msg)
            assert sfd is not None
            self.assertIsNone(getattr(sfd.metadata, field), f"field={field}")

            msg = base()
            msg['metadata']["generation_info"] = None
            sfd = parser.parse_get_loaded_sfd(msg)
            self.assertIsNone(sfd.metadata.generation_info.python_version)
            self.assertIsNone(sfd.metadata.generation_info.scrutiny_version)
            self.assertIsNone(sfd.metadata.generation_info.system_type)
            self.assertIsNone(sfd.metadata.generation_info.timestamp)

    def test_parse_get_server_stats(self):
        def base():
            return {
                'cmd': 'response_get_server_stats',
                'reqid': None,
                'uptime': 10.1,
                'invalid_request_count': 1,
                'unexpected_error_count': 2,
                'client_count': 3,
                'to_all_clients_datarate_byte_per_sec': 20.2,
                'from_any_client_datarate_byte_per_sec': 30.3,
                'msg_received': 4,
                'msg_sent': 5,
                'device_session_count': 6,
                'to_device_datarate_byte_per_sec': 40.4,
                'from_device_datarate_byte_per_sec': 50.5,
                'device_request_per_sec': 60.6
            }

        with self.assertRaises(Exception):
            m = base()
            m['cmd'] = 'asd'
            parser.parser_server_stats(m)

        msg = base()
        stats = parser.parser_server_stats(msg)

        self.assertEqual(stats.uptime, 10.1)
        self.assertEqual(stats.invalid_request_count, 1)
        self.assertEqual(stats.unexpected_error_count, 2)
        self.assertEqual(stats.client_count, 3)
        self.assertEqual(stats.to_all_clients_datarate_byte_per_sec, 20.2)
        self.assertEqual(stats.from_any_client_datarate_byte_per_sec, 30.3)
        self.assertEqual(stats.msg_received, 4)
        self.assertEqual(stats.msg_sent, 5)
        self.assertEqual(stats.device_session_count, 6)
        self.assertEqual(stats.to_device_datarate_byte_per_sec, 40.4)
        self.assertEqual(stats.from_device_datarate_byte_per_sec, 50.5)
        self.assertEqual(stats.device_request_per_sec, 60.6)

        all_fields = [
            'uptime',
            'invalid_request_count',
            'unexpected_error_count',
            'client_count',
            'to_all_clients_datarate_byte_per_sec',
            'from_any_client_datarate_byte_per_sec',
            'msg_received',
            'msg_sent',
            'device_session_count',
            'to_device_datarate_byte_per_sec',
            'from_device_datarate_byte_per_sec',
            'device_request_per_sec',
        ]

        float_field = [
            'uptime',
            'to_all_clients_datarate_byte_per_sec',
            'from_any_client_datarate_byte_per_sec',
            'to_device_datarate_byte_per_sec',
            'from_device_datarate_byte_per_sec',
            'device_request_per_sec'
        ]

        class Delete:
            pass

        for field in all_fields:
            for val in [None, [], {}, "asd", Delete]:
                msg = base()
                if val == Delete:
                    del msg[field]
                else:
                    msg[field] = val

                with self.assertRaises(sdk.exceptions.BadResponseError):
                    parser.parser_server_stats(msg)

        for field in float_field:
            for val in [1, 1.1]:
                # Make sure we accept int and converts to float
                msg = base()
                msg[field] = val

                stats = parser.parser_server_stats(msg)
                self.assertEqual(getattr(stats, field), val)
                self.assertIsInstance(getattr(stats, field), float)

    def test_parse_welcome(self):
        tnow = time.time()

        def base():
            return {
                "cmd": "welcome",
                "reqid": None,
                "server_time_zero_timestamp": tnow,
            }

        with self.assertRaises(Exception):
            m = base()
            m['cmd'] = 'asd'
            parser.parse_welcome(m)

        msg = base()
        welcome = parser.parse_welcome(msg)
        self.assertEqual(welcome.server_time_zero_timestamp, tnow)

    def test_parse_watchable_update(self):
        def base():
            return {
                'cmd': 'watchable_update',
                'req_id': None,
                'updates': [
                    dict(id='aaa', v=3.14159, t=1234.5),
                    dict(id='bbb', v=1, t=5555),
                    dict(id='ccc', v=True, t=6666)
                ]
            }

        with self.assertRaises(Exception):
            m = base()
            m['cmd'] = 'asd'
            parser.parse_watchable_update(m)

        msg = base()
        updates = parser.parse_watchable_update(msg)
        self.assertIsInstance(updates, list)
        self.assertEqual(len(updates), 3)
        for update in updates:
            self.assertIsInstance(update, parser.WatchableUpdate)
            self.assertIsInstance(update.server_id, str)
            self.assertIsInstance(update.value, (float, int, bool))
            self.assertIsInstance(update.server_time_us, float)

        self.assertEqual(updates[0].server_id, 'aaa')
        self.assertEqual(updates[0].value, 3.14159)
        self.assertIsInstance(updates[0].value, float)
        self.assertEqual(updates[0].server_time_us, 1234.5)

        self.assertEqual(updates[1].server_id, 'bbb')
        self.assertEqual(updates[1].value, 1)
        self.assertIsInstance(updates[1].value, int)
        self.assertEqual(updates[1].server_time_us, 5555)

        self.assertEqual(updates[2].server_id, 'ccc')
        self.assertEqual(updates[2].value, True)
        self.assertIsInstance(updates[2].value, bool)
        self.assertEqual(updates[2].server_time_us, 6666)

        class Delete:
            pass

        for v in [{}, None, 1, "asd", Delete]:
            msg = base()
            if v is Delete:
                del msg['updates']
            else:
                msg['updates'] = v
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"v={v}"):
                parser.parse_watchable_update(msg)

        for v in [{}, [], None, 1, Delete]:
            msg = base()
            for i in range(len(msg['updates'])):
                msg['updates'][i]['id'] = v
                with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"i={i}. v={v}"):
                    parser.parse_watchable_update(msg)

        for v in [{}, [], None, "asd", Delete]:
            msg = base()
            for i in range(len(msg['updates'])):
                msg['updates'][i]['v'] = v
                with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"i={i}. v={v}"):
                    parser.parse_watchable_update(msg)

        for v in [{}, [], None, True, "asd", Delete]:
            msg = base()
            for i in range(len(msg['updates'])):
                msg['updates'][i]['t'] = v
                with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"i={i}. v={v}"):
                    parser.parse_watchable_update(msg)

        msg = base()
        msg['updates'] = []
        updates = parser.parse_watchable_update(msg)
        self.assertEqual(updates, [])

    def test_parse_memory_read_completion(self):
        def base() -> api_typing.S2C.ReadMemoryComplete:
            return {
                'cmd': 'inform_memory_read_complete',
                "reqid": None,
                "request_token": "aaa",
                "success": True,
                "completion_server_time_us": 1234.5,
                "data": b64encode(bytes([1, 2, 3, 4])).decode('utf8'),
                "detail_msg": None
            }

        with self.assertRaises(Exception):
            m = base()
            m['cmd'] = 'asd'
            parser.parse_memory_read_completion(m)

        msg = base()
        completion = parser.parse_memory_read_completion(msg)

        self.assertEqual(completion.request_token, "aaa")
        self.assertEqual(completion.success, True)
        self.assertEqual(completion.data, bytes([1, 2, 3, 4]))
        self.assertIsInstance(completion.local_monotonic_timestamp, float)
        self.assertEqual(completion.server_time_us, 1234.5)
        self.assertEqual(completion.error, "")

        msg = base()
        msg['success'] = False
        del msg['data']
        completion = parser.parse_memory_read_completion(msg)
        self.assertEqual(completion.data, None)
        self.assertEqual(completion.success, False)

        class Delete:
            pass

        def check_field_invalid(field, vals):
            for val in vals:
                msg = base()
                if val is Delete:
                    del msg[field]
                else:
                    msg[field] = val

                with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"field={field}. val={val}"):
                    parser.parse_memory_read_completion(msg)

        check_field_invalid('request_token', [1, None, True, [], {}, Delete])
        check_field_invalid('success', [1, None, 1.123, "asd", [], {}, Delete])
        check_field_invalid('completion_server_time_us', ["asd", None, True, [], {}, Delete])
        check_field_invalid('data', [1, "...", None, True, [], {}, Delete])  # Cannot delete if success
        check_field_invalid('detail_msg', [1, 1.123, True, [], {}, Delete])

    def test_parse_memory_write_completion(self):
        def base() -> api_typing.S2C.WriteMemoryComplete:
            return {
                'cmd': 'inform_memory_write_complete',
                "reqid": None,
                "request_token": "aaa",
                "success": True,
                "completion_server_time_us": 1234.5,
                "detail_msg": None
            }

        with self.assertRaises(Exception):
            m = base()
            m['cmd'] = 'asd'
            parser.parse_memory_write_completion(m)

        msg = base()
        completion = parser.parse_memory_write_completion(msg)

        self.assertEqual(completion.request_token, "aaa")
        self.assertEqual(completion.success, True)
        self.assertIsInstance(completion.local_monotonic_timestamp, float)
        self.assertEqual(completion.server_time_us, 1234.5)
        self.assertEqual(completion.error, "")

        msg = base()
        msg['success'] = False
        completion = parser.parse_memory_write_completion(msg)
        self.assertEqual(completion.success, False)

        class Delete:
            pass

        def check_field_invalid(field, vals):
            for val in vals:
                msg = base()
                if val is Delete:
                    del msg[field]
                else:
                    msg[field] = val

                with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"field={field}. val={val}"):
                    parser.parse_memory_write_completion(msg)

        check_field_invalid('request_token', [1, None, True, [], {}, Delete])
        check_field_invalid('success', [1, None, 1.123, "asd", [], {}, Delete])
        check_field_invalid('completion_server_time_us', ["asd", None, True, [], {}, Delete])
        check_field_invalid('detail_msg', [1, 1.123, True, [], {}, Delete])

    def test_parse_inform_datalogging_list_changed(self):
        def base() -> api_typing.S2C.InformDataloggingListChanged:
            return {
                'cmd': 'inform_datalogging_list_changed',
                "reqid": None,
                "action": "new",
                "reference_id": "123456",
            }

        msg = base()
        parsed = parser.parse_datalogging_list_changed(msg)
        self.assertEqual(parsed.action, sdk.DataloggingListChangeType.NEW)
        self.assertEqual(parsed.reference_id, "123456")

        msg = base()
        msg['action'] = 'update'
        parsed = parser.parse_datalogging_list_changed(msg)
        self.assertEqual(parsed.action, sdk.DataloggingListChangeType.UPDATE)
        self.assertEqual(parsed.reference_id, "123456")

        msg = base()
        msg['action'] = 'delete'
        parsed = parser.parse_datalogging_list_changed(msg)
        self.assertEqual(parsed.action, sdk.DataloggingListChangeType.DELETE)
        self.assertEqual(parsed.reference_id, "123456")

        msg = base()
        msg['action'] = 'delete_all'
        msg['reference_id'] = None
        parsed = parser.parse_datalogging_list_changed(msg)
        self.assertEqual(parsed.action, sdk.DataloggingListChangeType.DELETE_ALL)
        self.assertIsNone(parsed.reference_id)

        class Delete:
            pass

        for v in ['unknown_val', 1, 2.2, None, [], {}, Delete]:
            with self.assertRaises(Exception):
                msg = base()
                if v == Delete:
                    del msg["action"]
                else:
                    msg["action"] = v
                parser.parse_datalogging_list_changed(msg)

        for v in [1, 2.2, [], {}, Delete]:
            with self.assertRaises(Exception):
                msg = base()
                if v == Delete:
                    del msg["reference_id"]
                else:
                    msg["reference_id"] = v
                parser.parse_datalogging_list_changed(msg)

        with self.assertRaises(Exception):
            msg = base()
            msg["action"] = 'new'
            msg["reference_id"] = None
            parser.parse_datalogging_list_changed(msg)

        with self.assertRaises(Exception):
            msg = base()
            msg["action"] = 'delete_all'
            msg["reference_id"] = 'asd'
            parser.parse_datalogging_list_changed(msg)

    def test_parse_request_datalogging_acquisition_response(self):
        def base() -> api_typing.S2C.RequestDataloggingAcquisition:
            return {
                'cmd': 'response_request_datalogging_acquisition',
                "reqid": None,
                "request_token": "abcdef"
            }

        msg = base()
        self.assertEqual(parser.parse_request_datalogging_acquisition_response(msg), "abcdef")

        class Delete:
            pass

        for v in [[], {}, None, 1, 2.2, True, Delete]:
            msg = base()
            if v == Delete:
                del msg['request_token']
            else:
                msg["request_token"] = v

            with self.assertRaises(sdk.exceptions.BadResponseError):
               	parser.parse_request_datalogging_acquisition_response(msg)

    def test_parse_datalogging_acquisition_complete(self):
        def base_success() -> api_typing.S2C.InformDataloggingAcquisitionComplete:
            return {
                "cmd": 'inform_datalogging_acquisition_complete',
                "success": True,
                "reference_id": "abc",
                "request_token": "xyz",
                "detail_msg": ""
            }

        def base_failure() -> api_typing.S2C.InformDataloggingAcquisitionComplete:
            return {
                "cmd": 'inform_datalogging_acquisition_complete',
                "success": False,
                "reference_id": None,
                "request_token": "xyz",
                "detail_msg": "oops"
            }

        msg = base_success()
        response = parser.parse_datalogging_acquisition_complete(msg)
        self.assertEqual(response.success, True)
        self.assertEqual(response.reference_id, "abc")
        self.assertEqual(response.request_token, "xyz")

        msg = base_failure()
        response = parser.parse_datalogging_acquisition_complete(msg)
        self.assertEqual(response.success, False)
        self.assertEqual(response.reference_id, None)
        self.assertEqual(response.request_token, "xyz")
        self.assertEqual(response.detail_msg, "oops")

        class Delete:
            pass

        for field in ['reference_id', 'request_token']:
            for v in [[], {}, None, 1, "", True, Delete]:
                msg = base_success()
                if v == Delete:
                    del msg[field]
                else:
                    msg[field] = v

                with self.assertRaises(sdk.exceptions.BadResponseError, msg=f'field={field}. v={v}'):
                    parser.parse_datalogging_acquisition_complete(msg)

        for v in [[], {}, None, 1, "", Delete]:
            msg = base_success()
            if v == Delete:
                del msg['success']
            else:
                msg['success'] = v

            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f'v={v}'):
                parser.parse_datalogging_acquisition_complete(msg)

        for v in [[], {}, None, 1, Delete]:
            msg = base_failure()
            if v == Delete:
                del msg['detail_msg']
            else:
                msg['detail_msg'] = v

            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f'v={v}'):
                parser.parse_datalogging_acquisition_complete(msg)

    def test_parse_user_command_response(self):
        def base() -> api_typing.S2C.UserCommand:
            return {
                "cmd": "response_user_command",
                "subfunction": 2,
                "data": b64encode(bytes([1, 2, 3])).decode('utf8')
            }

        msg = base()
        response = parser.parse_user_command_response(msg)
        self.assertEqual(response.subfunction, 2)
        self.assertEqual(response.data, bytes([1, 2, 3]))

        class Delete:
            pass

        for v in [[], {}, None, -1, 0x100, "", True, Delete]:
            msg = base()
            if v == Delete:
                del msg['subfunction']
            else:
                msg['subfunction'] = v

            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f'v={v}'):
                parser.parse_user_command_response(msg)

        for v in [[], {}, None, 1, "!!!", True, Delete]:
            msg = base()
            if v == Delete:
                del msg['data']
            else:
                msg['data'] = v

            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f'v={v}'):
                parser.parse_user_command_response(msg)

    def test_parse_write_value_response(self):
        def base() -> api_typing.S2C.WriteValue:
            return {
                'cmd': 'response_write_watchable',
                'count': 10,
                'request_token': 'abc'
            }

        msg = base()
        response = parser.parse_write_value_response(msg)
        self.assertEqual(response.count, 10)
        self.assertEqual(response.request_token, "abc")

        class Delete:
            pass

        for v in [[], {}, None, -1, 1.2, "", True, Delete]:
            msg = base()
            if v == Delete:
                del msg['count']
            else:
                msg['count'] = v

            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f'v={v}'):
                parser.parse_write_value_response(msg)

        for v in [[], {}, None, -1, 1.2, "", True, Delete]:
            msg = base()
            if v == Delete:
                del msg['request_token']
            else:
                msg['request_token'] = v

            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f'v={v}'):
                parser.parse_write_value_response(msg)

    def test_parse_write_completion(self):
        def base() -> api_typing.S2C.WriteCompletion:
            return {
                'cmd': 'inform_write_completion',
                'batch_index': 1,
                'completion_server_time_us': 123.4,
                'request_token': 'abc',
                'success': True,
                'watchable': "def"
            }

        msg = base()
        response = parser.parse_write_completion(msg)

        self.assertEqual(response.success, True)
        self.assertEqual(response.batch_index, 1)
        self.assertEqual(response.request_token, "abc")
        self.assertEqual(response.watchable, "def")
        self.assertEqual(response.server_time_us, 123.4)

        class Delete:
            pass

        for v in [[], {}, None, 1, 1.2, "", Delete]:
            msg = base()
            if v == Delete:
                del msg['success']
            else:
                msg['success'] = v

            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f'v={v}'):
                parser.parse_write_completion(msg)

        for v in [[], {}, None, 1.2, True, "aaa", Delete]:
            msg = base()
            if v == Delete:
                del msg['batch_index']
            else:
                msg['batch_index'] = v

            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f'v={v}'):
                parser.parse_write_completion(msg)

        for v in [[], {}, None, 1, True, 1.2, "", Delete]:
            msg = base()
            if v == Delete:
                del msg['request_token']
            else:
                msg['request_token'] = v

            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f'v={v}'):
                parser.parse_write_completion(msg)

        for v in [[], {}, None, 1, True, 1.2, "", Delete]:
            msg = base()
            if v == Delete:
                del msg['watchable']
            else:
                msg['watchable'] = v

            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f'v={v}'):
                parser.parse_write_completion(msg)

        for v in [[], {}, None, True, "asd", Delete]:
            msg = base()
            if v == Delete:
                del msg['completion_server_time_us']
            else:
                msg['completion_server_time_us'] = v

            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f'v={v}'):
                parser.parse_write_completion(msg)

    def test_parse_get_installed_sfds_response(self):
        now_timestamp = int(datetime.now().timestamp())

        def base() -> api_typing.S2C.GetInstalledSFD:
            return {
                "cmd": 'response_get_installed_sfd',
                "sfd_list": {
                    "firmware_id_1": {
                        'author': "AAA",
                        'version': "1.2.3",
                        'project_name': "BBB",
                        'generation_info': {
                            'python_version': "3.14.1",
                            'scrutiny_version': "1.2.3",
                            "system_type": "linux",
                            "time": now_timestamp
                        }
                    },
                    "firmware_id_2": {
                        'author': "CCC",
                        'version': "1.2.4",
                        'project_name': "DDD"
                    },
                    "firmware_id_3": {
                        'generation_info': {}
                    }
                }
            }

        msg = base()
        response = parser.parse_get_installed_sfds_response(msg)
        self.assertIsInstance(response, dict)
        self.assertEqual(len(response), 3)
        self.assertIn('firmware_id_1', response)
        self.assertIn('firmware_id_2', response)
        self.assertIn('firmware_id_3', response)

        sfd1 = response['firmware_id_1']
        sfd2 = response['firmware_id_2']
        sfd3 = response['firmware_id_3']

        self.assertIsInstance(sfd1, sdk.SFDInfo)
        self.assertEqual(sfd1.firmware_id, 'firmware_id_1')
        self.assertEqual(sfd1.metadata.author, 'AAA')
        self.assertEqual(sfd1.metadata.project_name, 'BBB')
        self.assertEqual(sfd1.metadata.version, '1.2.3')
        self.assertEqual(sfd1.metadata.generation_info.timestamp, datetime.fromtimestamp(now_timestamp))
        self.assertEqual(sfd1.metadata.generation_info.python_version, "3.14.1")
        self.assertEqual(sfd1.metadata.generation_info.scrutiny_version, "1.2.3")
        self.assertEqual(sfd1.metadata.generation_info.system_type, "linux")

        self.assertIsInstance(sfd2, sdk.SFDInfo)
        self.assertEqual(sfd2.firmware_id, 'firmware_id_2')
        self.assertEqual(sfd2.metadata.author, 'CCC')
        self.assertEqual(sfd2.metadata.project_name, 'DDD')
        self.assertEqual(sfd2.metadata.version, '1.2.4')
        self.assertIsNotNone(sfd2.metadata.generation_info)
        self.assertIsNone(sfd2.metadata.generation_info.python_version)
        self.assertIsNone(sfd2.metadata.generation_info.scrutiny_version)
        self.assertIsNone(sfd2.metadata.generation_info.system_type)
        self.assertIsNone(sfd2.metadata.generation_info.timestamp)

        self.assertIsInstance(sfd3, sdk.SFDInfo)
        self.assertEqual(sfd3.firmware_id, 'firmware_id_3')
        self.assertIsNone(sfd3.metadata.author)
        self.assertIsNone(sfd3.metadata.project_name)
        self.assertIsNone(sfd3.metadata.version)
        self.assertIsNotNone(sfd3.metadata.generation_info)
        self.assertIsNone(sfd3.metadata.generation_info.python_version)
        self.assertIsNone(sfd3.metadata.generation_info.scrutiny_version)
        self.assertIsNone(sfd3.metadata.generation_info.system_type)
        self.assertIsNone(sfd3.metadata.generation_info.timestamp)

        class Delete:
            pass

        for v in [[], None, 1.2, 1, True, Delete]:
            msg = base()
            if v == Delete:
                del msg["sfd_list"]
            else:
                msg["sfd_list"] = v

            with self.assertRaises(sdk.exceptions.BadResponseError):
                parser.parse_get_installed_sfds_response(msg)

        for field in ["author", "version", "project_name"]:
            msg = base()
            msg["sfd_list"]['firmware_id_1'][field] = None
            response = parser.parse_get_installed_sfds_response(msg)
            self.assertEqual(getattr(response['firmware_id_1'].metadata, field), None)

            msg = base()
            del msg["sfd_list"]['firmware_id_1'][field]
            response = parser.parse_get_installed_sfds_response(msg)
            self.assertEqual(getattr(response['firmware_id_1'].metadata, field), None)

            for v in [[], {}, 1.2, 1, True]:
                msg = base()
                msg["sfd_list"]['firmware_id_1'][field] = v
                with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"field={field}. v={v}"):
                    parser.parse_get_installed_sfds_response(msg)


if __name__ == '__main__':
    unittest.main()
