#    test_device_handler.py
#        Test the DeviceHandler that manage the communication with the device at high level.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2023 Scrutiny Debugger

import time
from scrutiny.core.codecs import Encodable
from scrutiny.server.datastore.datastore_entry import DatastoreRPVEntry, EntryType
from test import logger
import signal  # For ctrl+c handling
import struct
import random
from binascii import hexlify

import scrutiny.server.datalogging.definitions.device as device_datalogging
from scrutiny.server.device.emulated_device import EmulatedDevice
from scrutiny.server.device.device_handler import DeviceHandler
from scrutiny.server.device.links.dummy_link import ThreadSafeDummyLink
from scrutiny.server.datastore.datastore import Datastore
from scrutiny.server.datastore.datastore_entry import *
from scrutiny.server.datastore.entry_type import EntryType
from scrutiny.core.variable import Variable
from scrutiny.core.codecs import Codecs
from scrutiny.core.basic_types import *
from scrutiny.server.device.device_info import *
from scrutiny.server.datalogging.datalogging_utilities import extract_signal_from_data
from test import ScrutinyUnitTest, logger

from scrutiny.core.typehints import GenericCallback
from typing import cast, List

no_callback = UpdateTargetRequestCallback(lambda *args, **kwargs: None)


def d2f(d):
    return struct.unpack('f', struct.pack('f', d))[0]


def generate_random_value(datatype: EmbeddedDataType) -> Encodable:
    # Generate random bitstring of the right size. Then decode it.
    codec = Codecs.get(datatype, Endianness.Big)
    if datatype in [EmbeddedDataType.float8, EmbeddedDataType.float16, EmbeddedDataType.float32, EmbeddedDataType.float64, EmbeddedDataType.float128, EmbeddedDataType.float256]:
        return codec.decode(codec.encode((random.random() - 0.5) * 1000))

    bytestr = bytes([random.randint(0, 0xff) for i in range(datatype.get_size_byte())])
    return codec.decode(bytestr)


class TestDeviceHandler(ScrutinyUnitTest):
    def ctrlc_handler(self, signal, frame):
        if self.emulated_device is not None:
            self.emulated_device.stop()
        raise KeyboardInterrupt

    def setUp(self):
        self.acquisition_complete_callback_called = False
        self.acquisition_complete_callback_success = None
        self.acquisition_complete_callback_data = None
        self.acquisition_complete_callback_metadata = None
        self.acquisition_complete_callback_details = None
        self.datastore = Datastore()
        config = {
            'link_type': 'thread_safe_dummy',
            'link_config': {},
            'response_timeout': 0.25,
            'heartbeat_timeout': 2
        }

        self.device_handler = DeviceHandler(config, self.datastore)
        self.link = self.device_handler.get_comm_link()
        self.emulated_device = EmulatedDevice(self.link)
        self.emulated_device.start()

        signal.signal(signal.SIGINT, self.ctrlc_handler)    # Clean exit on Ctrl+C

    def tearDown(self):
        self.emulated_device.stop()

    def disconnect_callback(self, clean_disconnect):
        self.disconnect_callback_called = True
        self.disconnect_was_clean = clean_disconnect

    def test_connect_disconnect_normal(self):
        self.disconnect_callback_called = False
        self.disconnect_was_clean = False
        timeout = 2
        t1 = time.time()
        connection_successful = False
        disconnect_sent = False
        while time.time() - t1 < timeout:
            self.device_handler.process()
            time.sleep(0.01)
            status = self.device_handler.get_connection_status()
            self.assertEqual(self.device_handler.get_comm_error_count(), 0)

            if status in [DeviceHandler.ConnectionStatus.CONNECTED_NOT_READY or DeviceHandler.ConnectionStatus.CONNECTED_READY]:
                connection_successful = True

                if not disconnect_sent:
                    self.assertTrue(self.emulated_device.connected)
                    disconnect_sent = True
                    self.device_handler.send_disconnect(self.disconnect_callback)

            if self.disconnect_callback_called:
                break

        self.assertTrue(connection_successful)
        self.assertTrue(self.disconnect_callback_called)
        self.assertTrue(self.disconnect_was_clean)

    def test_establish_full_connection_and_hold(self):
        setup_timeout = 2
        hold_time = 10
        t1 = time.time()
        connection_successful = False
        hold_time_set = False
        timeout = setup_timeout
        while time.time() - t1 < timeout:
            self.device_handler.process()
            time.sleep(0.01)
            status = self.device_handler.get_connection_status()
            self.assertEqual(self.device_handler.get_comm_error_count(), 0)

            if status == DeviceHandler.ConnectionStatus.CONNECTED_READY:
                self.assertIsNotNone(self.device_handler.get_comm_session_id())
                connection_successful = True
                if hold_time_set == False:
                    hold_time_set = True
                    timeout = hold_time
                    t1 = time.time()
            else:
                self.assertIsNone(self.device_handler.get_comm_session_id())

            if connection_successful:
                self.assertTrue(status == DeviceHandler.ConnectionStatus.CONNECTED_READY)
                self.assertTrue(self.emulated_device.is_connected())

        self.assertTrue(connection_successful)

    def test_read_correct_params(self):
        timeout = 3
        t1 = time.time()
        connection_successful = False
        while time.time() - t1 < timeout:
            self.device_handler.process()
            time.sleep(0.01)
            status = self.device_handler.get_connection_status()

            if status == DeviceHandler.ConnectionStatus.CONNECTED_READY:
                connection_successful = True
                break

        self.assertTrue(connection_successful)
        info = self.device_handler.get_device_info()

        self.assertEqual(info.protocol_major, self.emulated_device.protocol.version_major)
        self.assertEqual(info.protocol_minor, self.emulated_device.protocol.version_minor)
        self.assertEqual(info.max_rx_data_size, self.emulated_device.max_rx_data_size)
        self.assertEqual(info.max_tx_data_size, self.emulated_device.max_tx_data_size)
        self.assertEqual(info.max_bitrate_bps, self.emulated_device.max_bitrate_bps)
        self.assertEqual(info.heartbeat_timeout_us, self.emulated_device.heartbeat_timeout_us)
        self.assertEqual(info.rx_timeout_us, self.emulated_device.rx_timeout_us)
        self.assertEqual(info.address_size_bits, self.emulated_device.address_size_bits)
        self.assertEqual(info.supported_feature_map['memory_write'], self.emulated_device.supported_features['memory_write'])
        self.assertEqual(info.supported_feature_map['datalogging'], self.emulated_device.supported_features['datalogging'])
        self.assertEqual(info.supported_feature_map['user_command'], self.emulated_device.supported_features['user_command'])
        self.assertEqual(info.supported_feature_map['_64bits'], self.emulated_device.supported_features['_64bits'])

        for region in self.emulated_device.forbidden_regions:
            found = False
            for region2 in info.forbidden_memory_regions:
                if region2['start'] == region['start'] and region2['end'] == region['end']:
                    found = True

            self.assertTrue(found)

        for region in self.emulated_device.readonly_regions:
            found = False
            for region2 in info.readonly_memory_regions:
                if region2['start'] == region['start'] and region2['end'] == region['end']:
                    found = True
            self.assertTrue(found)

        self.assertEqual(len(info.loops), len(self.emulated_device.loops))

        for i in range(len(info.loops)):
            received_loop = info.loops[i]
            expected_loop = self.emulated_device.loops[i]

            self.assertIsInstance(received_loop, expected_loop.__class__)
            self.assertEqual(received_loop.get_name(), expected_loop.get_name())
            self.assertEqual(received_loop.get_loop_type(), expected_loop.get_loop_type())
            self.assertEqual(received_loop.support_datalogging, expected_loop.support_datalogging)

            if isinstance(received_loop, FixedFreqLoop):
                assert isinstance(expected_loop, FixedFreqLoop)
                self.assertEqual(received_loop.get_timestep_100ns(), expected_loop.get_timestep_100ns())
                self.assertEqual(received_loop.freq, expected_loop.freq)

    def test_auto_disconnect_if_comm_interrupted(self):
        timeout = 5     # Should take about 2.5 sec to disconnect With heartbeat at every 2 sec
        t1 = time.time()
        connection_completed = False
        connection_lost = False
        while time.time() - t1 < timeout:
            self.device_handler.process()
            time.sleep(0.01)
            status = self.device_handler.get_connection_status()

            if status == DeviceHandler.ConnectionStatus.CONNECTED_READY and connection_completed == False:
                connection_completed = True
                self.assertEqual(self.device_handler.get_comm_error_count(), 0)
                self.emulated_device.disable_comm()  # Eventually, the device handler will notice that the device doesn't speak anymore and will auto-disconnect

            if connection_completed:
                if status != DeviceHandler.ConnectionStatus.CONNECTED_READY:
                    connection_lost = True
                    break

        self.assertTrue(connection_lost)

    def test_auto_disconnect_if_device_disconnect(self):
        # Should behave exactly the same as test_auto_disconnect_if_comm_interrupted
        timeout = 5     # Should take about 2.5 sec to disconnect With heartbeat at every 2 sec
        t1 = time.time()
        connection_completed = False
        connection_lost = False
        while time.time() - t1 < timeout:
            self.device_handler.process()
            time.sleep(0.01)
            status = self.device_handler.get_connection_status()

            if status == DeviceHandler.ConnectionStatus.CONNECTED_READY and connection_completed == False:
                connection_completed = True
                self.assertEqual(self.device_handler.get_comm_error_count(), 0)
                self.emulated_device.force_disconnect()

            if connection_completed:
                if status != DeviceHandler.ConnectionStatus.CONNECTED_READY:
                    connection_lost = True
                    break

        self.assertTrue(connection_lost)

    def test_auto_disconnect_and_reconnect_on_broken_link(self):
        timeout = 5     # Should take about 2.5 sec to disconnect With heartbeat at every 2 sec
        t1 = time.time()
        connection_completed = False
        connection_lost = False
        connection_recovered = False
        while time.time() - t1 < timeout:
            self.device_handler.process()
            time.sleep(0.01)
            status = self.device_handler.get_connection_status()

            if status == DeviceHandler.ConnectionStatus.CONNECTED_READY and connection_completed == False:
                connection_completed = True
                self.assertEqual(self.device_handler.get_comm_error_count(), 0)
                self.device_handler.get_comm_link().emulate_broken = True

            if connection_completed:
                if status != DeviceHandler.ConnectionStatus.CONNECTED_READY:
                    if connection_lost == False:
                        self.emulated_device.force_disconnect()  # So that next connection works right away without getting responded with a "Busy"
                        self.device_handler.get_comm_link().emulate_broken = False
                    connection_lost = True

            if connection_lost:
                if status == DeviceHandler.ConnectionStatus.CONNECTED_READY:
                    connection_recovered = True
                    break

        self.assertTrue(connection_lost)
        self.assertTrue(connection_recovered)

    def test_throttling(self):
        timeout = 3
        measurement_time = 10
        target_bitrate = 5000
        self.emulated_device.max_bitrate_bps = target_bitrate
        self.device_handler.set_operating_mode(DeviceHandler.OperatingMode.Test_CheckThrottling)
        connect_time = None
        t1 = time.time()
        while time.time() - t1 < timeout:
            self.device_handler.process()
            status = self.device_handler.get_connection_status()
            if status == DeviceHandler.ConnectionStatus.CONNECTED_READY and connect_time is None:
                self.device_handler.reset_bitrate_monitor()
                connect_time = time.time()
                self.assertTrue(self.device_handler.is_throttling_enabled())
                self.assertEqual(self.device_handler.get_throttling_bitrate(), self.emulated_device.max_bitrate_bps)
                t1 = time.time()
                timeout = measurement_time

        self.assertIsNotNone(connect_time)
        measured_bitrate = self.device_handler.get_average_bitrate()
        logger.info('Measured bitrate = %0.2fkbps. Target = %0.2fkbps' % (measured_bitrate / 1000.0, target_bitrate / 1000.0))
        self.assertLess(measured_bitrate, target_bitrate * 1.5)
        self.assertGreater(measured_bitrate, target_bitrate / 1.5)

    # Check that the datastore is correctly synchronized with a fake memory in the emulated device.

    def test_read_write_variables(self):
        vfloat32 = DatastoreVariableEntry('dummy_float32',
                                          variable_def=Variable(
                                              'dummy_float32',
                                              vartype=EmbeddedDataType.float32,
                                              path_segments=[],
                                              location=0x10000,
                                              endianness=Endianness.Little)
                                          )

        vint64 = DatastoreVariableEntry('dummy_sint64',
                                        variable_def=Variable(
                                            'dummy_sint64',
                                            vartype=EmbeddedDataType.sint64,
                                            path_segments=[],
                                            location=0x10010,
                                            endianness=Endianness.Little)
                                        )

        vbool = DatastoreVariableEntry('dummy_bool',
                                       variable_def=Variable(
                                           'dummy_bool',
                                           vartype=EmbeddedDataType.boolean,
                                           path_segments=[],
                                           location=0x10020,
                                           endianness=Endianness.Little)
                                       )

        self.datastore.add_entry(vfloat32)
        self.datastore.add_entry(vint64)
        self.datastore.add_entry(vbool)

        test_round_to_do = 5
        setup_timeout = 2
        hold_timeout = 5
        t1 = time.time()
        connection_successful = False
        timeout = setup_timeout
        time_margin = 0.1

        round_completed = 0
        state = 'init_memory'
        while time.time() - t1 < timeout and round_completed < test_round_to_do:
            self.device_handler.process()
            status = self.device_handler.get_connection_status()
            self.assertEqual(self.device_handler.get_comm_error_count(), 0)

            if status == DeviceHandler.ConnectionStatus.CONNECTED_READY:
                if connection_successful == False:
                    timeout = hold_timeout
                    connection_successful = True

                    self.datastore.start_watching(vfloat32, watcher='unittest')
                    self.datastore.start_watching(vint64, watcher='unittest')
                    self.datastore.start_watching(vbool, watcher='unittest')

                if state == 'init_memory':
                    self.emulated_device.write_memory(0x10000, struct.pack('<f', 3.1415926))
                    self.emulated_device.write_memory(0x10010, struct.pack('<q', 0x123456789abcdef))
                    self.emulated_device.write_memory(0x10020, struct.pack('<b', 1))
                    init_memory_time = time.time()
                    state = 'read_memory'

                elif state == 'read_memory':
                    value_updated = (vfloat32.get_value_change_timestamp() > init_memory_time + time_margin) and (vint64.get_value_change_timestamp() >
                                                                                                                  init_memory_time + time_margin) and (vbool.get_value_change_timestamp() > init_memory_time + time_margin)

                    if value_updated:
                        self.assertEqual(vfloat32.get_value(), d2f(3.1415926), 'round=%d' % round_completed)
                        self.assertEqual(vint64.get_value(), 0x123456789abcdef, 'round=%d' % round_completed)
                        self.assertEqual(vbool.get_value(), True, 'round=%d' % round_completed)

                        self.datastore.update_target_value(vfloat32, 2.7, no_callback)
                        self.datastore.update_target_value(vint64, 0x1122334455667788, no_callback)
                        self.datastore.update_target_value(vbool, False, no_callback)

                        write_time = time.time()
                        state = 'write_memory'

                    elif time.time() - init_memory_time > 1:
                        raise Exception('Value did not update')

                elif state == 'write_memory':
                    value_updated = True
                    value_updated = value_updated and (vfloat32.get_last_target_update_timestamp() is not None) and (
                        vfloat32.get_last_target_update_timestamp() > write_time)
                    value_updated = value_updated and (vint64.get_last_target_update_timestamp() is not None) and (
                        vint64.get_last_target_update_timestamp() > write_time)
                    value_updated = value_updated and (vbool.get_last_target_update_timestamp() is not None) and (
                        vbool.get_last_target_update_timestamp() > write_time)

                    if value_updated:
                        self.assertEqual(vfloat32.get_value(), d2f(2.7), 'round=%d' % round_completed)
                        self.assertEqual(vint64.get_value(), 0x1122334455667788, 'round=%d' % round_completed)
                        self.assertEqual(vbool.get_value(), False, 'round=%d' % round_completed)

                        self.assertEqual(self.emulated_device.read_memory(0x10000, 4), struct.pack('<f', d2f(2.7)))
                        self.assertEqual(self.emulated_device.read_memory(0x10010, 8), struct.pack('<q', 0x1122334455667788))
                        self.assertEqual(self.emulated_device.read_memory(0x10020, 1), struct.pack('<b', 0))

                        round_completed += 1
                        state = 'init_memory'

                    elif time.time() - write_time > 1:
                        raise Exception('Value not written')

            # Make sure we don't disconnect
            if connection_successful:
                self.assertTrue(status == DeviceHandler.ConnectionStatus.CONNECTED_READY)
                self.assertTrue(self.emulated_device.is_connected())

            time.sleep(0.01)

        self.assertTrue(connection_successful)
        self.assertEqual(round_completed, test_round_to_do)  # Check that we made 5 cycles of value

    def test_discover_read_write_rpvs(self):
        test_round_to_do = 5
        setup_timeout = 2
        hold_timeout = 5

        timeout = setup_timeout
        round_completed = 0
        t1 = time.time()
        all_entries = []
        write_timestamp = 0
        write_from_device_timestamp = 0
        state = 'wait_for_connection'

        while time.time() - t1 < timeout and round_completed < test_round_to_do:
            self.device_handler.process()

            status = self.device_handler.get_connection_status()
            self.assertEqual(self.device_handler.get_comm_error_count(), 0)

            if status == DeviceHandler.ConnectionStatus.CONNECTED_READY:
                if state == 'wait_for_connection':
                    timeout = hold_timeout

                    self.assertEqual(self.datastore.get_entries_count(EntryType.Var), 0)
                    self.assertEqual(self.datastore.get_entries_count(EntryType.Alias), 0)
                    self.assertEqual(self.datastore.get_entries_count(EntryType.RuntimePublishedValue), len(self.emulated_device.rpvs))

                    all_entries = cast(List[DatastoreRPVEntry], list(self.datastore.get_all_entries(EntryType.RuntimePublishedValue)))

                    for entry in all_entries:
                        assert isinstance(entry, DatastoreRPVEntry)
                        self.datastore.start_watching(entry, watcher='unittest')

                    state = 'write'
                    round_completed = 0

                if state == 'write':
                    previous_write_timestamp_per_entry = {}
                    
                    written_values = {}
                    for entry in all_entries:
                        previous_write_timestamp_per_entry[entry.get_id()] = entry.get_last_target_update_timestamp()
                    time.sleep(0.05)
                    for entry in all_entries:
                        rpv = entry.get_rpv()
                        written_values[rpv.id] = generate_random_value(rpv.datatype)
                        self.datastore.update_target_value(entry, written_values[rpv.id], no_callback)
                    
                    state = 'wait_for_update_and_validate'

                elif state == 'wait_for_update_and_validate':
                    all_updated = True
                    for entry in all_entries:
                        last_update_timestamp = entry.get_last_target_update_timestamp()
                        if last_update_timestamp is None or last_update_timestamp == previous_write_timestamp_per_entry[entry.get_id()]:
                            all_updated = False
                        else:
                            rpv = entry.get_rpv()
                            self.assertEqual(entry.get_value(), written_values[rpv.id], "rpv=0x%04x" % rpv.id)

                    if all_updated:
                        written_values = {}
                        state = 'write_from_device'

                elif state == 'write_from_device':
                    written_values = {}
                    for rpv in self.emulated_device.get_rpvs():
                        written_values[rpv.id] = generate_random_value(rpv.datatype)
                        self.emulated_device.write_rpv(rpv.id, written_values[rpv.id])
                    
                    time.sleep(0.05)
                    previous_write_timestamp_per_entry ={}
                    for entry in all_entries:
                        previous_write_timestamp_per_entry[entry.get_id()] = entry.get_value_change_timestamp()
                    state = 'wait_for_update_and_read'

                elif state == 'wait_for_update_and_read':
                    all_updated = True
                    for entry in all_entries:
                        rpv = entry.get_rpv()
                        if entry.get_value_change_timestamp() == previous_write_timestamp_per_entry[entry.get_id()]:
                            all_updated = False
                        else:

                            self.assertEqual(entry.get_value(), written_values[rpv.id])

                    if all_updated:
                        state = 'done'
                        written_values = {}

                elif state == 'done':
                    round_completed += 1
                    time.sleep(0.02)
                    state = 'write'

        self.assertEqual(round_completed, test_round_to_do)  # Make sure test went through.

    def acquisition_complete_callback(self, success: bool, details: str, data: Optional[List[List[bytes]]], metadata: Optional[device_datalogging.AcquisitionMetadata]):
        logger.debug('acquisition_complete_callback called. success=%s.' % (success))
        self.acquisition_complete_callback_called = True
        self.acquisition_complete_callback_success = success
        self.acquisition_complete_callback_data = data
        self.acquisition_complete_callback_metadata = metadata
        self.acquisition_complete_callback_details = details

    def test_datalogging_device_disabled(self):
        # Make sure that the device handler does nothing with datalogging when the device doesn't support it

        self.emulated_device.disable_datalogging()
        self.assertFalse(self.emulated_device.is_datalogging_enabled(), "Datalogging is disabled on emulated device.")

        timeout = 4
        t1 = time.time()
        connection_completed = False
        while time.time() - t1 < timeout:
            self.device_handler.process()
            time.sleep(0.01)
            status = self.device_handler.get_connection_status()
            if status == DeviceHandler.ConnectionStatus.CONNECTED_READY and connection_completed == False:
                connection_completed = True
                break
        self.assertTrue(connection_completed)
        device_info = self.device_handler.get_device_info()
        assert device_info is not None
        self.assertFalse(device_info.supported_feature_map['datalogging'])
        self.assertFalse(self.device_handler.datalogging_poller.is_enabled())

        t1 = time.time()
        while time.time() - t1 < 0.5:
            self.device_handler.process()   # Keep processing to see if datalogging feature will do something (it should not)

        self.assertIsNone(self.device_handler.get_datalogging_setup())   # Should never be set

    def test_datalogging_control_normal_behavior(self):
        # Test the behavior of the datalogging poller

        # Make sure this is enabled, otherwise, the test is useless and will fail.
        self.assertTrue(self.emulated_device.is_datalogging_enabled())

        config = device_datalogging.Configuration()
        config.trigger_hold_time = 0
        config.timeout = 0
        config.probe_location = 0.5
        config.decimation = 1
        config.trigger_condition = device_datalogging.TriggerCondition(
            device_datalogging.TriggerConditionID.Equal,
            device_datalogging.RPVOperand(rpv_id=0x1000),
            device_datalogging.LiteralOperand(12345678)
        )
        config.add_signal(device_datalogging.TimeLoggableSignal())
        config.add_signal(device_datalogging.RPVLoggableSignal(0x1003))
        config.add_signal(device_datalogging.MemoryLoggableSignal(address=0x100000, size=4))
        config.add_signal(device_datalogging.MemoryLoggableSignal(address=0x100004, size=2))
        config.add_signal(device_datalogging.MemoryLoggableSignal(address=0x100006, size=2))

        # Not ready yet.
        self.assertFalse(self.device_handler.is_ready_for_datalogging_acquisition_request())

        with self.assertRaises(Exception):
            self.device_handler.request_datalogging_acquisition(0, config, self.acquisition_complete_callback)

        for iteration in range(6):
            self.acquisition_complete_callback_called = False
            logger.debug("[iteration=%d] Wait for connection" % iteration)
            # First we wait on connection to be ready with the device
            timeout = 3
            t1 = time.time()
            connection_completed = False
            while time.time() - t1 < timeout:
                self.device_handler.process()
                time.sleep(0.01)
                status = self.device_handler.get_connection_status()
                if status == DeviceHandler.ConnectionStatus.CONNECTED_READY and connection_completed == False:
                    connection_completed = True
                    break

            timeout = 1
            t1 = time.time()
            while time.time() - t1 < timeout:
                self.device_handler.process()
                time.sleep(0.01)
                if self.device_handler.get_datalogger_state() is not None:
                    break

            self.assertIsNotNone(self.device_handler.get_datalogger_state(), "iteration=%d" % iteration)
            # Make sure everything is idle after connection
            self.assertTrue(connection_completed)
            device_info = self.device_handler.get_device_info()
            assert device_info is not None
            self.assertTrue(device_info.supported_feature_map['datalogging'])
            self.assertTrue(self.device_handler.datalogging_poller.is_enabled())
            if iteration == 0:
                self.assertEqual(self.device_handler.get_datalogger_state(), device_datalogging.DataloggerState.IDLE)

            # Next wait for datalogging poller to retrieve the configuration of the datalogging feature
            logger.debug("[iteration=%d] Wait for setup" % iteration)
            timeout = 2
            t1 = time.time()
            datalogging_setup = None
            while time.time() - t1 < timeout:
                self.device_handler.process()
                datalogging_setup = self.device_handler.get_datalogging_setup()
                if datalogging_setup is not None and self.device_handler.is_ready_for_datalogging_acquisition_request():  # Expect setup to be read
                    break

            self.assertIsNotNone(datalogging_setup)

            self.assertTrue(self.device_handler.is_ready_for_datalogging_acquisition_request())
            self.assertEqual(datalogging_setup.buffer_size, self.emulated_device.datalogger.get_buffer_size())
            self.assertEqual(datalogging_setup.encoding, self.emulated_device.datalogger.get_encoding())
            self.assertEqual(datalogging_setup.max_signal_count, self.emulated_device.datalogger.MAX_SIGNAL_COUNT)

            # Make sure nothing happens unless somebody require an acquisition
            self.device_handler.process()
            time.sleep(0.1)
            self.device_handler.process()
            if iteration == 0:
                self.assertEqual(self.device_handler.get_datalogger_state(), device_datalogging.DataloggerState.IDLE)

            self.emulated_device.write_memory(0x100000, bytes([1, 2, 3, 4, 5, 6, 7, 8]))
            self.emulated_device.write_rpv(0x1000, 0)
            self.emulated_device.write_rpv(0x1003, 123)

            # Prepare a request for acquisition
            loop_name = "Variable Freq 1"
            loop_id = None
            for i in range(len(device_info.loops)):
                if device_info.loops[i].get_name() == loop_name:
                    loop_id = i
                    break
            assert loop_id is not None

            # Give the acquisition request to the device handler
            if iteration != 5:
                # A new request is made mid-loop on iteration 4, so we don't override it
                logger.debug("[iteration=%d] Requesting a new acquisition" % iteration)
                self.device_handler.request_datalogging_acquisition(loop_id, config, self.acquisition_complete_callback)

            if iteration == 3:
                self.device_handler.process()
                self.assertFalse(self.acquisition_complete_callback_called)
                logger.debug("[iteration=%d] Requesting a new acquisition to interrupt previous one" % iteration)

                with self.assertRaises(RuntimeError):
                    self.device_handler.request_datalogging_acquisition(loop_id, config, self.acquisition_complete_callback)

                self.device_handler.cancel_datalogging_acquisition()
                self.assertTrue(self.device_handler.datalogging_cancel_in_progress())
                timeout = 1
                t1 = time.time()
                while self.device_handler.datalogging_cancel_in_progress() and time.time() - t1 < timeout:
                    self.device_handler.process()
                self.assertFalse(self.device_handler.datalogging_cancel_in_progress())

                self.device_handler.request_datalogging_acquisition(loop_id, config, self.acquisition_complete_callback)
                self.assertTrue(self.acquisition_complete_callback_called)
                self.assertFalse(self.acquisition_complete_callback_success)
                self.acquisition_complete_callback_called = False
                self.acquisition_complete_callback_success = False

            # Make sure it is received and that the device is waiting for the trigger to happen
            logger.debug("[iteration=%d] Wait for armed" % iteration)
            timeout = 1
            t1 = time.time()
            while time.time() - t1 < timeout:
                self.device_handler.process()
                if self.device_handler.get_datalogger_state() == device_datalogging.DataloggerState.ARMED:
                    break

            # This test did fail once for no apparent reason. Stinks of race condition...
            self.assertEqual(self.device_handler.get_datalogger_state(), device_datalogging.DataloggerState.ARMED, 'iteration=%d' % iteration)

            if iteration == 4:
                logger.debug("[iteration=%d] Requesting a new acquisition to interrupt previous one" % iteration)
                with self.assertRaises(RuntimeError):
                    self.device_handler.request_datalogging_acquisition(loop_id, config, self.acquisition_complete_callback)

                self.device_handler.cancel_datalogging_acquisition()
                self.assertTrue(self.device_handler.datalogging_cancel_in_progress())
                timeout = 1
                t1 = time.time()
                while self.device_handler.datalogging_cancel_in_progress() and time.time() - t1 < timeout:
                    self.device_handler.process()
                self.assertFalse(self.device_handler.datalogging_cancel_in_progress())

                self.device_handler.request_datalogging_acquisition(loop_id, config, self.acquisition_complete_callback)
                self.assertTrue(self.acquisition_complete_callback_called)
                self.assertFalse(self.acquisition_complete_callback_success)
                self.acquisition_complete_callback_called = False
                self.acquisition_complete_callback_success = False
                continue    #

            # Make sure it stays it the same state if the trigger never happens
            t1 = time.time()
            while time.time() - t1 < 0.5:
                self.device_handler.process()
                time.sleep(0.05)

            self.assertEqual(self.device_handler.get_datalogger_state(), device_datalogging.DataloggerState.ARMED, 'iteration=%d' % iteration)
            self.assertFalse(self.acquisition_complete_callback_called, 'iteration=%d' % iteration)
            self.assertFalse(self.emulated_device.datalogger.triggered(), 'iteration=%d' % iteration)

            # Now we fulfill the trigger condition,  the acquisition should complete and data be automatically downloaded.
            logger.debug("[iteration=%d] Make trigger condition true" % iteration)
            self.emulated_device.write_rpv(0x1000, 12345678)

            logger.debug("[iteration=%d] Wait for acquisition complete" % iteration)
            timeout = 2
            t1 = time.time()
            while time.time() - t1 < timeout:
                self.device_handler.process()
                time.sleep(0.01)
                if self.acquisition_complete_callback_called:
                    break
            nb_points = self.emulated_device.datalogger.get_nb_points()
            # Make sure acquisition is downloaded and device is in a good state
            self.assertGreater(nb_points, 0, 'iteration=%d' % iteration)
            self.assertTrue(self.emulated_device.datalogger.triggered(), 'iteration=%d' % iteration)
            self.assertTrue(self.acquisition_complete_callback_called, "Acquired %d points" % nb_points)
            self.assertTrue(self.acquisition_complete_callback_success)
            signals = extract_signal_from_data(
                data=self.emulated_device.datalogger.get_acquisition_data(),
                config=config,
                rpv_map=self.emulated_device.get_rpv_definition_map(),
                encoding=datalogging_setup.encoding
            )
            self.assertEqual(self.acquisition_complete_callback_data, signals, 'iteration=%d' % iteration)
            self.assertEqual(self.acquisition_complete_callback_metadata.data_size, len(self.emulated_device.datalogger.get_acquisition_data()))
            self.assertIsInstance(self.acquisition_complete_callback_details, str)
            trigger_point_precision = 1 / self.acquisition_complete_callback_metadata.number_of_points
            computed_trigger_position = 1 - self.acquisition_complete_callback_metadata.points_after_trigger / self.acquisition_complete_callback_metadata.number_of_points
            self.assertLessEqual(computed_trigger_position, config.probe_location + trigger_point_precision)
            self.assertGreaterEqual(computed_trigger_position, config.probe_location - trigger_point_precision)

            self.assertEqual(len(signals), 5)
            for signal in signals:
                self.assertEqual(len(signal), nb_points)

            # RPV 1003: 8bits val = 123
            for d in signals[1]:
                self.assertEqual(struct.unpack('>B', d)[0], 123, 'iteration=%d' % iteration)

            # Memory: 32bits val = 1,2,3,4
            for d in signals[2]:
                self.assertEqual(d, bytes([1, 2, 3, 4]), 'iteration=%d' % iteration)

            # Memory: 16bits val = 5,6
            for d in signals[3]:
                self.assertEqual(d, bytes([5, 6]), 'iteration=%d' % iteration)

            # Memory: 16bits val = 7,8
            for d in signals[4]:
                self.assertEqual(d, bytes([7, 8]), 'iteration=%d' % iteration)


class TestDeviceHandlerMultipleLink(ScrutinyUnitTest):

    def ctrlc_handler(self, signal, frame):
        if self.emulated_device1 is not None:
            self.emulated_device1.stop()

        if self.emulated_device2 is not None:
            self.emulated_device2.stop()
        raise KeyboardInterrupt

    def setUp(self):

        self.datastore = Datastore()
        config = {
            'response_timeout': 0.25,
            'heartbeat_timeout': 2
        }

        self.device_handler = DeviceHandler(config, self.datastore)
        self.assertIsNone(self.device_handler.get_comm_link())
        self.link1 = ThreadSafeDummyLink.make({'channel_id': 1})
        self.link2 = ThreadSafeDummyLink.make({'channel_id': 2})

        self.emulated_device1 = EmulatedDevice(self.link1)
        self.emulated_device2 = EmulatedDevice(self.link2)
        self.emulated_device1.start()
        self.emulated_device2.start()

        signal.signal(signal.SIGINT, self.ctrlc_handler)    # Clean exit on Ctrl+C

    def tearDown(self):
        self.emulated_device1.stop()
        self.emulated_device2.stop()

    def test_change_link_mid_comm(self):
        # This test failed once on CI for no reason.  Keep an eye on it!   self.assertTrue(connection_completed) == flase

        # Make sur ewe can work with no link
        self.device_handler.process()
        self.device_handler.process()
        self.device_handler.process()

        self.assertIsNone(self.device_handler.get_comm_link())

        self.device_handler.configure_comm('thread_safe_dummy', {'channel_id': 1})

        # Should behave exactly the same as test_auto_disconnect_if_comm_interrupted
        timeout = 5     # Should take about 2.5 sec to disconnect With heartbeat at every 2 sec
        t1 = time.time()
        connection_completed = False
        while time.time() - t1 < timeout:
            self.device_handler.process()
            time.sleep(0.01)
            status = self.device_handler.get_connection_status()

            if status == DeviceHandler.ConnectionStatus.CONNECTED_READY and connection_completed == False:
                connection_completed = True
                break

        self.assertTrue(connection_completed)
        self.assertTrue(self.emulated_device1.is_connected())
        self.assertFalse(self.emulated_device2.is_connected())
        self.assertEqual(self.device_handler.get_comm_error_count(), 0)

        self.device_handler.configure_comm('thread_safe_dummy', {'channel_id': 2})
        self.device_handler.process()
        self.assertNotEqual(self.device_handler.get_connection_status(), DeviceHandler.ConnectionStatus.CONNECTED_READY)

        timeout = 5     # Should take about 2.5 sec to disconnect With heartbeat at every 2 sec
        t1 = time.time()
        connection_completed = False
        while time.time() - t1 < timeout:
            self.device_handler.process()
            time.sleep(0.01)
            status = self.device_handler.get_connection_status()

            if status == DeviceHandler.ConnectionStatus.CONNECTED_READY and connection_completed == False:
                connection_completed = True
                break

        self.assertTrue(connection_completed)
        # self.assertTrue(self.emulated_device1.is_connected())
        self.assertTrue(self.emulated_device2.is_connected())
        self.assertEqual(self.device_handler.get_comm_error_count(), 0)


if __name__ == '__main__':
    import unittest
    unittest.main()
