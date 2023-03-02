#    test_datalogging_integration.py
#        Test the whole datalogging chain with a request to the API, a server that process
#        the request and a fake device that will do the logging.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2023 Scrutiny Debugger

import struct

from scrutiny.server.api import API
import scrutiny.server.api.typing as api_typing
from scrutiny.core.sfd_storage import SFDStorage
from scrutiny.server.datastore.datastore_entry import *
from scrutiny.core.basic_types import *
from scrutiny.core.codecs import *
from scrutiny.server.device.device_info import *
from typing import List, cast
from scrutiny.server.datalogging.datalogging_storage import DataloggingStorage
from binascii import hexlify

from test.integration.integration_test import ScrutinyIntegrationTestWithTestSFD1
from test import logger


def d2f(d: float) -> float:
    return struct.unpack('f', struct.pack('f', d))[0]


def diff(sig: List[float]) -> List[float]:
    if len(sig) <= 1:
        return []

    out = [None] * (len(sig) - 1)
    for i in range(1, len(sig)):
        out[i - 1] = sig[i] - sig[i - 1]
    return out


class TestDataloggingIntegration(ScrutinyIntegrationTestWithTestSFD1):

    def setUp(self):
        super().setUp()
        self.wait_for_datalogging_ready()

    def wait_for_datalogging_ready(self):
        timeout = 2
        t1 = time.time()
        while time.time() - t1 < timeout:
            self.server.process()
            if self.server.device_handler.is_ready_for_datalogging_acquisition_request():
                break
            time.sleep(0.05)
        self.assertTrue(self.server.device_handler.is_ready_for_datalogging_acquisition_request())

    def test_setup_is_working(self):
        self.do_test_setup_is_working()

        info = self.server.device_handler.get_device_info()
        assert info is not None
        self.assertTrue(info.supported_feature_map['datalogging'])

    def init_device_memory(self, entries: List[DatastoreEntry]):
        for entry in entries:
            if isinstance(entry, DatastoreVariableEntry):
                self.emulated_device.write_memory(entry.get_address(), b'\x00' * entry.get_size())

    def test_get_datalogger_capabilities(self):
        req = {
            'cmd': API.Command.Client2Api.GET_SERVER_STATUS,
        }
        self.send_request(req)
        response = cast(api_typing.S2C.InformServerStatus, self.wait_and_load_response(cmd=API.Command.Api2Client.INFORM_SERVER_STATUS))
        self.assertIn('device_datalogging_status', response)
        status = response['device_datalogging_status']
        assert status is not None
        self.assertIn('datalogger_state', status)
        self.assertIn('completion_ratio', status)
        self.assertEqual(status['datalogger_state'], "standby")

        req = {
            'cmd': API.Command.Client2Api.GET_DATALOGGING_CAPABILITIES
        }

        self.send_request(req)
        response = cast(api_typing.S2C.GetDataloggingCapabilities, self.wait_and_load_response(
            cmd=API.Command.Api2Client.GET_DATALOGGING_CAPABILITIES_RESPONSE))

        self.assertTrue(response['available'])
        self.assertIsNotNone(response['capabilities'])
        capabilities = response['capabilities']
        self.assertEqual(capabilities['buffer_size'], self.emulated_device.datalogger.get_buffer_size())
        self.assertEqual(capabilities['max_nb_signal'], self.emulated_device.datalogger.MAX_SIGNAL_COUNT)

        if self.emulated_device.datalogger.get_encoding() == self.emulated_device.datalogger.encoding.RAW:
            self.assertEqual(capabilities['encoding'], 'raw')
        else:
            raise NotImplementedError('Unsupported encoding')

        expected_sampling_rates = []
        for i in range(len(self.emulated_device.loops)):
            loop = self.emulated_device.loops[i]
            if loop.support_datalogging:
                loop_obj = {
                    'identifier': i,
                    'name': loop.get_name()
                }
                if isinstance(loop, FixedFreqLoop):
                    loop_obj['frequency'] = loop.get_frequency()
                    loop_obj['type'] = 'fixed_freq'
                elif isinstance(loop, VariableFreqLoop):
                    loop_obj['type'] = 'variable_freq'
                    loop_obj['frequency'] = None
                else:
                    raise NotImplementedError('Unsupported loop type')

                expected_sampling_rates.append(loop_obj)

        self.assertEqual(len(capabilities['sampling_rates']), len(expected_sampling_rates))    # Emulated device has 4 loops, 3 supports datalogging

        for i in range(len(expected_sampling_rates)):
            self.assertEqual(capabilities['sampling_rates'][i], expected_sampling_rates[i])

    def test_make_acquisition_normal(self):
        with DataloggingStorage.use_temp_storage():
            # We will create  a task that the emulated device will run in its thread. This task update some memory region with known pattern.
            class ValueUpdateTask:
                def __init__(self, testcase: ScrutinyIntegrationTestWithTestSFD1):
                    self.last_update = time.time()
                    self.update_counter = 0
                    self.u32_addr = testcase.entry_u32.get_address()
                    self.f32_addr = testcase.entry_float32.get_address()
                    self.u8_addr = testcase.entry_u8.get_address()
                    self.device = testcase.emulated_device

                def __call__(self):
                    t = time.time()
                    if t - self.last_update > 0.005:
                        codec_u32 = Codecs.get(EmbeddedDataType.uint32, Endianness.Little)
                        val = codec_u32.decode(self.device.read_memory(self.u32_addr, 4))
                        val = (val + 10) & 0xFFFFFFFF
                        self.device.write_memory(self.u32_addr, codec_u32.encode(val))

                        codec_f32 = Codecs.get(EmbeddedDataType.float32, Endianness.Little)
                        v = (self.update_counter % 4) * 100
                        self.device.write_memory(self.f32_addr, codec_f32.encode(v))

                        codec_u8 = Codecs.get(EmbeddedDataType.uint8, Endianness.Little)
                        val = codec_u8.decode(self.device.read_memory(self.u8_addr, 1))
                        val = (val + 1) & 0xFF
                        self.device.write_memory(self.u8_addr, codec_u8.encode(val))

                        self.device.write_rpv(0x1000, self.device.read_rpv(0x1000) + 5)  # RPV 1000 is a float64
                        self.last_update = t
                        self.update_counter += 1

            for iteration in range(3):
                logger.debug("test_make_acquisition_normal iteration=%d" % iteration)
                # First make sure there is no acquisition in storage
                self.send_request({
                    'cmd': API.Command.Client2Api.LIST_DATALOGGING_ACQUISITION,
                    'firmware_id': self.emulated_device.get_firmware_id_ascii()
                })
                response = self.wait_and_load_response(API.Command.Api2Client.LIST_DATALOGGING_ACQUISITION_RESPONSE)
                self.assert_no_error(response)
                response = cast(api_typing.S2C.ListDataloggingAcquisition, response)
                self.assertEqual(len(response['acquisitions']), iteration)

                # Request acquisition
                loop_id = 1
                self.assertGreater(len(self.emulated_device.loops), loop_id)
                self.assertTrue(self.emulated_device.loops[loop_id].support_datalogging)

                decimation = 2
                req: api_typing.C2S.RequestDataloggingAcquisition = {
                    'cmd': API.Command.Client2Api.REQUEST_DATALOGGING_ACQUISITION,
                    'reqid': 123,
                    'name': 'potato',
                    'decimation': decimation,
                    'probe_location': 0.25,
                    'trigger_hold_time': 0.2,
                    'sampling_rate_id': loop_id,
                    'timeout': 0,
                    'condition': 'eq',
                    'yaxis': [
                        {'name': 'Axis1', 'id': 100},
                        {'name': 'Axis2', 'id': 200}
                    ],
                    'operands': [
                        {
                            'type': 'watchable',
                            'value': self.entry_u16.get_id()
                        },
                        {
                            'type': 'literal',
                            'value': 0x1234
                        }],
                    'signals': [
                        dict(id=self.entry_u32.get_id(), name='u32', axis_id=100),
                        dict(id=self.entry_float32.get_id(), name='f32', axis_id=100),
                        dict(id=self.entry_alias_rpv1000.get_id(), name='rpv1000', axis_id=200),
                        dict(id=self.entry_alias_uint8.get_id(), name='u8', axis_id=200)
                    ],
                    'x_axis_type': 'measured_time',
                    'x_axis_signal': None,    # We use time
                }

                self.assertEqual(self.emulated_device.get_rpv_definition(0x1000).datatype, EmbeddedDataType.float64)
                self.emulated_device.write_memory(self.entry_u32.get_address(), bytes([0, 0, 0, 0]))
                self.emulated_device.write_memory(self.entry_float32.get_address(), bytes([0, 0, 0, 0]))
                self.emulated_device.write_memory(self.entry_u8.get_address(), bytes([0]))
                self.emulated_device.write_memory(self.entry_u16.get_address(), bytes([0, 0]))
                self.emulated_device.write_rpv(0x1000, 0)

                if iteration == 0:
                    self.emulated_device.add_additional_task(ValueUpdateTask(self))  # Will be run in device thread

                self.send_request(req)  # Send the acquisition request here
                self.ensure_no_response_for(0.2)

                self.wait_for(1)
                self.assertFalse(self.emulated_device.datalogger.triggered())
                self.assertFalse(self.api_conn.from_server_available())
                # This line should trigger the acquisition
                self.emulated_device.write_memory(self.entry_u16.get_address(), Codecs.get(EmbeddedDataType.uint16, Endianness.Little).encode(0x1234))
                self.wait_for(req['trigger_hold_time'] + 0.1)  # Leave some time for the device thread to catch the change.
                logger.debug("ID = %s. Address=%d" % (self.entry_u16.get_id(), self.entry_u16.get_address()))
                logger.debug('data=%s' % hexlify(self.emulated_device.read_memory(self.entry_u16.get_address(), 2)))

                self.assertTrue(self.emulated_device.datalogger.triggered())

                acq_refid = None
                received_req = {
                    API.Command.Api2Client.INFORM_DATALOGGING_LIST_CHANGED: None,
                    API.Command.Api2Client.REQUEST_DATALOGGING_ACQUISITION_RESPONSE: None,
                }
                for i in range(2):
                    response = self.wait_and_load_response(
                        cmd=[
                            API.Command.Api2Client.INFORM_DATALOGGING_LIST_CHANGED,
                            API.Command.Api2Client.REQUEST_DATALOGGING_ACQUISITION_RESPONSE
                        ], timeout=2.0)

                    self.assert_no_error(response)
                    received_req[response['cmd']] = True
                    if response['cmd'] == API.Command.Api2Client.INFORM_DATALOGGING_LIST_CHANGED:
                        response = cast(api_typing.S2C.InformDataloggingListChanged, response)
                        self.assertEqual(response['action'], 'new')
                        if acq_refid is not None:
                            self.assertEqual(acq_refid, response['reference_id'])
                        else:
                            acq_refid = response['reference_id']

                    elif response['cmd'] == API.Command.Api2Client.REQUEST_DATALOGGING_ACQUISITION_RESPONSE:
                        response = cast(api_typing.S2C.RequestDataloggingAcquisition, response)
                        self.assertEqual(response['reqid'], req['reqid'])
                        self.assertTrue(response['success'])
                        if acq_refid is not None:
                            self.assertEqual(acq_refid, response['reference_id'])
                        else:
                            acq_refid = response['reference_id']
                    else:
                        raise ValueError("Unexpected response %s" % response)

                # Make sure we received both response above.
                for k in received_req:
                    self.assertIsNotNone(received_req[k])

                # We got notified by the server. Now let's poll the datalogging database and see what's in there. We expect a new recording
                self.send_request({
                    'cmd': API.Command.Client2Api.LIST_DATALOGGING_ACQUISITION,
                    'firmware_id': self.emulated_device.get_firmware_id_ascii()
                })

                response = self.wait_and_load_response(cmd=API.Command.Api2Client.LIST_DATALOGGING_ACQUISITION_RESPONSE)
                self.assert_no_error(response)
                response = cast(api_typing.S2C.ListDataloggingAcquisition, response)

                self.assertEqual(len(response['acquisitions']), iteration + 1)

                found = False
                for acq_summary in response['acquisitions']:
                    if acq_summary['reference_id'] == acq_refid:
                        found = True
                        self.assertEqual(acq_summary['firmware_id'], self.emulated_device.get_firmware_id_ascii())
                        self.assertEqual(acq_summary['name'], 'potato')
                        self.assertEqual(acq_summary['reference_id'], acq_refid)
                        self.assertEqual(acq_summary['firmware_metadata'], None)
                        break

                self.assertTrue(found)

                # Let's read the content of that single acquisition
                self.send_request({
                    'cmd': API.Command.Client2Api.READ_DATALOGGING_ACQUISITION_CONTENT,
                    'reqid': 456,
                    'reference_id': acq_refid
                })

                response = self.wait_and_load_response(cmd=API.Command.Api2Client.READ_DATALOGGING_ACQUISITION_CONTENT_RESPONSE)
                self.assert_no_error(response)
                response = cast(api_typing.S2C.ReadDataloggingAcquisitionContent, response)

                self.assertEqual(response['reference_id'], acq_refid)
                self.assertEqual(len(response['signals']), 4)

                # Check that all signals has the same number of points, including x axis
                all_signals = response['signals']
                all_signals.append(response['xdata'])
                nb_points = None
                for signal in all_signals:
                    if nb_points is None:
                        nb_points = len(signal['data'])
                    else:
                        self.assertEqual(len(signal['data']), nb_points)

                self.assertEqual(response['xdata']['name'], 'X-Axis')
                self.assertEqual(len(response['yaxis']), 2)
                self.assertEqual(response['yaxis'][0]['name'], "Axis1")
                self.assertEqual(response['yaxis'][0]['id'], 100)
                self.assertEqual(response['yaxis'][1]['name'], "Axis2")
                self.assertEqual(response['yaxis'][1]['id'], 200)

                self.assertEqual(response['signals'][0]['name'], 'u32')
                self.assertEqual(response['signals'][1]['name'], 'f32')
                self.assertEqual(response['signals'][2]['name'], 'rpv1000')
                self.assertEqual(response['signals'][3]['name'], 'u8')

                self.assertEqual(response['signals'][0]['logged_element'], self.entry_u32.get_display_path())
                self.assertEqual(response['signals'][1]['logged_element'], self.entry_float32.get_display_path())
                self.assertEqual(response['signals'][2]['logged_element'], self.entry_alias_rpv1000.get_display_path())
                self.assertEqual(response['signals'][3]['logged_element'], self.entry_alias_uint8.get_display_path())

                self.assertEqual(response['signals'][0]['axis_id'], 100)
                self.assertEqual(response['signals'][1]['axis_id'], 100)
                self.assertEqual(response['signals'][2]['axis_id'], 200)
                self.assertEqual(response['signals'][3]['axis_id'], 200)

                timediff = diff(response['xdata']['data'])
                for val in timediff:
                    self.assertGreater(val, 0)  # Time should always increase

                sig = response['signals'][0]['data']
                expected_val = sig[0]
                for val in sig:
                    self.assertEqual(expected_val, val)
                    expected_val = (expected_val + 10 * decimation) % 0xFFFFFFFF

                self.assertLess(decimation, 4)  # required for this test to work
                sig = response['signals'][1]['data']
                expected_val = sig[0]
                self.assertTrue(expected_val in [0, 100, 200, 300])
                for val in sig:
                    self.assertEqual(expected_val, val)
                    expected_val += 100 * decimation
                    if expected_val > 300:
                        expected_val -= 400

                sig = response['signals'][2]['data']
                expected_val = sig[0]
                for val in sig:
                    self.assertEqual(expected_val, val)
                    expected_val = expected_val + decimation * 5 * self.entry_alias_rpv1000.aliasdef.get_gain()

                sig = response['signals'][3]['data']
                expected_val = sig[0]
                for val in sig:
                    self.assertAlmostEqual(expected_val, val, 4)
                    expected_val = (expected_val + 1 * decimation * self.entry_alias_uint8.aliasdef.get_gain()) % 0xFF

    def tearDown(self) -> None:
        super().tearDown()


if __name__ == '__main__':
    import unittest
    unittest.main()
