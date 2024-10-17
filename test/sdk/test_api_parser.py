#    test_api_parser.py
#        Test suite for the parsing function used by the client
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import unittest

import scrutiny.sdk._api_parser as parser
from scrutiny.core.basic_types import *
from scrutiny.sdk.definitions import *
import scrutiny.server.api.typing as api_typing
import scrutiny.sdk
import scrutiny.sdk.datalogging
sdk = scrutiny.sdk  # Workaround for vscode linter an submodule on alias
from copy import copy
from datetime import datetime, timedelta
import logging
from test import ScrutinyUnitTest
from typing import *


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
                            "name" : "example_enum",
                            "values" : {
                                "aaa" : 1,
                                "bbb" : 2,
                                "ccc" : 3
                            }
                        }
                    },{
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
                        'enum' : {
                            'name' : 'the_enum',
                            'values' : {
                                'a' : 1,
                                'b' : 2,
                                'c' : 3,
                            }
                        }
                    }
                }
            }

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

    def test_parse_inform_server_status(self):
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
                with self.assertRaises(sdk.exceptions.BadResponseError):
                    msg = base()
                    msg['device_info']['supported_feature_map'][feature] = val
                    parser.parse_inform_server_status(msg)

        for feature in features:
            logging.debug(f"feature={feature}")
            with self.assertRaises(sdk.exceptions.BadResponseError):
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

        with self.assertRaises(sdk.exceptions.BadResponseError):
            msg = base()
            msg['device_status'] = "asd"
            parser.parse_inform_server_status(msg)

        with self.assertRaises(sdk.exceptions.BadResponseError):
            msg = base()
            msg["device_info"]['forbidden_memory_regions'][0]['end'] = msg["device_info"]['forbidden_memory_regions'][0]['start'] - 1
            info = parser.parse_inform_server_status(msg)

        with self.assertRaises(sdk.exceptions.BadResponseError):
            msg = base()
            msg["device_info"]['readonly_memory_regions'][0]['end'] = msg["device_info"]['readonly_memory_regions'][0]['start'] - 1
            info = parser.parse_inform_server_status(msg)

        fields = ['max_tx_data_size', 'max_rx_data_size', 'max_bitrate_bps', 'rx_timeout_us', 'heartbeat_timeout_us',
                  'address_size_bits', 'protocol_major', 'protocol_minor']
        for field in fields:
            vals = ['asd', 1.5, [], {},]   # bad values
            for val in vals:
                logging.debug(f"field={field}, val={val}")
                with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"field={field}, val={val}"):
                    msg = base()
                    msg["device_info"][field] = val
                    info = parser.parse_inform_server_status(msg)

        msg = base()
        msg["device_info"]["max_bitrate_bps"] = None
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
            'stopbits': '2'
        }
        # We forgot to update the config.
        info = parser.parse_inform_server_status(msg)

        self.assertEqual(info.device_link.type, DeviceLinkType.Serial)
        self.assertEqual(info.device_link.config.baudrate, 9600)
        self.assertEqual(info.device_link.config.databits, sdk.SerialLinkConfig.DataBits.EIGHT)
        self.assertEqual(info.device_link.config.parity, sdk.SerialLinkConfig.Parity.EVEN)
        self.assertEqual(info.device_link.config.port, '/dev/ttyO1')
        self.assertEqual(info.device_link.config.stopbits, sdk.SerialLinkConfig.StopBits.TWO)

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
                with self.assertRaises(sdk.exceptions.BadResponseError):
                    msg["device_comm_link"]["link_config"][field] = val
                    parser.parse_inform_server_status(msg)

        for field in field_vals:
            msg = copy(serial_base)
            logging.debug(f"field={field}")
            with self.assertRaises(sdk.exceptions.BadResponseError):
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
                with self.assertRaises(sdk.exceptions.BadResponseError):
                    msg["device_comm_link"]["link_config"][field] = val
                    parser.parse_inform_server_status(msg)

        for field in field_vals:
            msg = base()
            logging.debug(f"field={field}")
            with self.assertRaises(sdk.exceptions.BadResponseError):
                del msg["device_comm_link"]["link_config"][field]
                parser.parse_inform_server_status(msg)

    def test_parse_datalogging_capabilities(self):
        def base() -> api_typing.S2C.GetDataloggingCapabilities:
            return {
                "cmd": "get_datalogging_capabilities_response",
                "reqid": None,
                "available": True,
                "capabilities": {
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

        msg = base()
        capabilities = parser.parse_get_datalogging_capabilities_response(msg)

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

        msg = base()
        msg["available"] = False
        self.assertIsNone(parser.parse_get_datalogging_capabilities_response(msg))

        msg = base()
        msg["available"] = False
        msg["capabilities"] = None
        self.assertIsNone(parser.parse_get_datalogging_capabilities_response(msg))

        msg = base()
        msg["capabilities"] = "asd"
        with self.assertRaises(sdk.exceptions.BadResponseError):
            self.assertIsNone(parser.parse_get_datalogging_capabilities_response(msg))

        msg = base()
        msg["capabilities"]["encoding"] = "asd"
        with self.assertRaises(sdk.exceptions.BadResponseError):
            self.assertIsNone(parser.parse_get_datalogging_capabilities_response(msg))

        msg = base()
        msg["capabilities"]["sampling_rates"][0]["type"] = "asdasd"
        with self.assertRaises(sdk.exceptions.BadResponseError):
            self.assertIsNone(parser.parse_get_datalogging_capabilities_response(msg))

    def test_parse_read_datalogging_acquisition_content(self):
        now = datetime.now()

        def base() -> api_typing.S2C.ReadDataloggingAcquisitionContent:
            return {
                "cmd": "read_datalogging_acquisition_content_response",
                "reqid": None,
                "firmware_id": "foo",
                "firmware_name": "hello",
                "name": "acquisition 123",
                "reference_id": "bar.baz",
                "trigger_index": 5,
                "timestamp": now.timestamp(),
                "xdata": {
                    "name": "Xaxis",
                    "logged_element": "path/to/xaxis/item",
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
                        "logged_element": "/path/to/signal1",
                        "data": [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
                    },
                    {
                        "axis_id": 0,
                        "name": "signal2",
                        "logged_element": "/path/to/signal2",
                        "data": [0, -10, -20, -30, -40, -50, -60, -70, -80, -90]
                    },
                    {
                        "axis_id": 1,
                        "name": "signal3",
                        "logged_element": "/path/to/signal3",
                        "data": [-4.5, -3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5, 4.5]
                    }
                ]
            }

        msg = base()
        acq = parser.parse_read_datalogging_acquisition_content_response(msg)

        self.assertIsInstance(acq, sdk.datalogging.DataloggingAcquisition)
        self.assertEqual(acq.firmware_id, "foo")
        self.assertEqual(acq.firmware_name, 'hello')
        self.assertEqual(acq.name, "acquisition 123")
        self.assertEqual(acq.reference_id, "bar.baz")
        self.assertLessEqual(abs(acq.acq_time - now), timedelta(seconds=1))

        self.assertEqual(acq.xdata.name, "Xaxis")
        self.assertEqual(acq.xdata.logged_element, "path/to/xaxis/item")
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
        self.assertEqual(data[0].series.logged_element, "/path/to/signal1")

        self.assertIn(data[1].axis.axis_id, yaxes_map)
        self.assertEqual(yaxes_map[data[1].axis.axis_id].name, "Y-Axis1")
        self.assertEqual(data[1].series.name, "signal2")
        self.assertEqual(data[1].series.logged_element, "/path/to/signal2")

        self.assertIn(data[2].axis.axis_id, yaxes_map)
        self.assertEqual(yaxes_map[data[2].axis.axis_id].name, "Y-Axis2")
        self.assertEqual(data[2].series.name, "signal3")
        self.assertEqual(data[2].series.logged_element, "/path/to/signal3")

        for field in ['firmware_id', 'firmware_name', 'name', 'reference_id', 'trigger_index', 'timestamp', 'xdata', 'yaxes', 'signals']:
            msg = base()
            del msg[field]
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"Field : {field}"):
                parser.parse_read_datalogging_acquisition_content_response(msg)

        for field in ['name', 'logged_element', 'data']:
            msg = base()
            del msg['xdata'][field]
            with self.assertRaises(sdk.exceptions.BadResponseError, msg=f"Field : {field}"):
                parser.parse_read_datalogging_acquisition_content_response(msg)

        for field in ['axis_id', 'name', 'logged_element', 'data']:
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

            for val in [3, None, {}, []]:
                msg = base()
                msg['signals'][i]["logged_element"] = val
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
                "cmd": "list_datalogging_acquisitions_response",
                "reqid": None,
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

        # SFD metadata is user generated. We must be super resilient to garbage.
        for val in [[], 1, True, {}]:
            msg = base()
            msg["acquisitions"][0]["firmware_metadata"]["author"] = val
            parser.parse_list_datalogging_acquisitions_response(msg)

        for val in [[], 1, True, {}]:
            msg = base()
            msg["acquisitions"][0]["firmware_metadata"]["project_name"] = val
            parser.parse_list_datalogging_acquisitions_response(msg)

        for val in [[], 1, True, {}]:
            msg = base()
            msg["acquisitions"][0]["firmware_metadata"]["version"] = val
            parser.parse_list_datalogging_acquisitions_response(msg)

        for val in [[], 1, True, {}]:
            msg = base()
            msg["acquisitions"][0]["firmware_metadata"]["generation_info"]["python_version"] = val
            parser.parse_list_datalogging_acquisitions_response(msg)

        for val in [[], 1, True, {}]:
            msg = base()
            msg["acquisitions"][0]["firmware_metadata"]["generation_info"]["scrutiny_version"] = val

        for val in [[], 1, True, {}]:
            msg = base()
            msg["acquisitions"][0]["firmware_metadata"]["generation_info"]["system_type"] = val
            parser.parse_list_datalogging_acquisitions_response(msg)

        for val in ["asd", [], True, {}]:
            msg = base()
            msg["acquisitions"][0]["firmware_metadata"]["generation_info"]["time"] = val
            parser.parse_list_datalogging_acquisitions_response(msg)

    def test_parse_get_watchable_count(self):
        def base():
            return {
                "cmd": "response_get_watchable_count",
                "reqid": None,
                'qty' : {
                    'alias' : 10,
                    'var' : 20,
                    'rpv' : 30,
                }
            }
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


if __name__ == '__main__':
    unittest.main()
