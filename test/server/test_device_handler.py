#    test_device_handler.py
#        Test the DeviceHandler that manage the communication with the device at high level.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import unittest
from time import time, sleep
from test import logger
import signal  # For ctrl+c handling

from scrutiny.server.device.emulated_device import EmulatedDevice
from scrutiny.server.device.device_handler import DeviceHandler
from scrutiny.server.device.links.dummy_link import ThreadSafeDummyLink
from scrutiny.server.datastore import Datastore, DatastoreEntry
from scrutiny.server.protocol.commands import DummyCommand
from scrutiny.server.protocol import Request, Response
from scrutiny.core import *

from scrutiny.core.typehints import GenericCallback


def d2f(d):
    return struct.unpack('f', struct.pack('f', d))[0]


class TestDeviceHandler(unittest.TestCase):
    def ctrlc_handler(self, signal, frame):
        if self.emulated_device is not None:
            self.emulated_device.stop()
        raise KeyboardInterrupt

    def setUp(self):
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
        self.device_handler.stop_comm()

    def test_connect_disconnect_normal(self):
        self.disconnect_callback_called = False
        self.disconnect_was_clean = False
        timeout = 1
        t1 = time()
        connection_successful = False
        disconnect_sent = False
        while time() - t1 < timeout:
            self.device_handler.process()
            sleep(0.01)
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
        t1 = time()
        connection_successful = False
        hold_time_set = False
        timeout = setup_timeout
        while time() - t1 < timeout:
            self.device_handler.process()
            sleep(0.01)
            status = self.device_handler.get_connection_status()
            self.assertEqual(self.device_handler.get_comm_error_count(), 0)

            if status == DeviceHandler.ConnectionStatus.CONNECTED_READY:
                connection_successful = True
                if hold_time_set == False:
                    hold_time_set = True
                    timeout = hold_time
                    t1 = time()

            if connection_successful:
                self.assertTrue(status == DeviceHandler.ConnectionStatus.CONNECTED_READY)
                self.assertTrue(self.emulated_device.is_connected())

        self.assertTrue(connection_successful)

    def test_read_correct_params(self):
        timeout = 3
        t1 = time()
        connection_successful = False
        while time() - t1 < timeout:
            self.device_handler.process()
            sleep(0.01)
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
        self.assertEqual(info.supported_feature_map['datalog_acquire'], self.emulated_device.supported_features['datalog_acquire'])
        self.assertEqual(info.supported_feature_map['user_command'], self.emulated_device.supported_features['user_command'])

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

    def test_auto_disconnect_if_comm_interrupted(self):
        timeout = 5     # Should take about 2.5 sec to disconnect With heartbeat at every 2 sec
        t1 = time()
        connection_completed = False
        connection_lost = False
        while time() - t1 < timeout:
            self.device_handler.process()
            sleep(0.01)
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
        t1 = time()
        connection_completed = False
        connection_lost = False
        while time() - t1 < timeout:
            self.device_handler.process()
            sleep(0.01)
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

    def test_auto_diconnect_and_reconnect_on_broken_link(self):
        timeout = 5     # Should take about 2.5 sec to disconnect With heartbeat at every 2 sec
        t1 = time()
        connection_completed = False
        connection_lost = False
        connection_recovered = False
        while time() - t1 < timeout:
            self.device_handler.process()
            sleep(0.01)
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
        t1 = time()
        while time() - t1 < timeout:
            self.device_handler.process()
            status = self.device_handler.get_connection_status()
            if status == DeviceHandler.ConnectionStatus.CONNECTED_READY and connect_time is None:
                self.device_handler.reset_bitrate_monitor()
                connect_time = time()
                self.assertTrue(self.device_handler.is_throttling_enabled())
                self.assertEqual(self.device_handler.get_throttling_bitrate(), self.emulated_device.max_bitrate_bps)
                t1 = time()
                timeout = measurement_time

        self.assertIsNotNone(connect_time)
        measured_bitrate = self.device_handler.get_average_bitrate()
        logger.info('Measured bitrate = %0.2fkbps. Target = %0.2fkbps' % (measured_bitrate / 1000.0, target_bitrate / 1000.0))
        self.assertLess(measured_bitrate, target_bitrate * 1.5)
        self.assertGreater(measured_bitrate, target_bitrate / 1.5)

    # Check that the datastore is correctly synchronized with a fake memory in the emulated device.

    def test_read_write_variables(self):
        vfloat32 = DatastoreEntry(DatastoreEntry.EntryType.Var, 'dummy_float32', variable_def=Variable(
            'dummy_float32', vartype=VariableType.float32, path_segments=[], location=0x10000, endianness=Endianness.Little))
        vint64 = DatastoreEntry(DatastoreEntry.EntryType.Var, 'dummy_sint64', variable_def=Variable(
            'dummy_sint64', vartype=VariableType.sint64, path_segments=[], location=0x10010, endianness=Endianness.Little))
        vbool = DatastoreEntry(DatastoreEntry.EntryType.Var, 'dummy_bool', variable_def=Variable(
            'dummy_bool', vartype=VariableType.boolean, path_segments=[], location=0x10020, endianness=Endianness.Little))

        self.datastore.add_entry(vfloat32)
        self.datastore.add_entry(vint64)
        self.datastore.add_entry(vbool)

        dummy_callback = GenericCallback(lambda *args, **kwargs: None)

        test_round_to_do = 5
        setup_timeout = 2
        hold_timeout = 5
        t1 = time()
        connection_successful = False
        timeout = setup_timeout
        connection_time = None
        time_margin = 0.1

        round_completed = 0
        state = 'init_memory'
        while time() - t1 < timeout and round_completed < test_round_to_do:
            self.device_handler.process()
            status = self.device_handler.get_connection_status()
            self.assertEqual(self.device_handler.get_comm_error_count(), 0)

            if status == DeviceHandler.ConnectionStatus.CONNECTED_READY:
                if connection_successful == False:
                    timeout = hold_timeout
                    connection_time = time()
                    connection_successful = True

                    self.datastore.start_watching(vfloat32, watcher='unittest', callback=dummy_callback)
                    self.datastore.start_watching(vint64, watcher='unittest', callback=dummy_callback)
                    self.datastore.start_watching(vbool, watcher='unittest', callback=dummy_callback)

                if state == 'init_memory':
                    self.emulated_device.write_memory(0x10000, struct.pack('<f', 3.1415926))
                    self.emulated_device.write_memory(0x10010, struct.pack('<q', 0x123456789abcdef))
                    self.emulated_device.write_memory(0x10020, struct.pack('<b', 1))
                    init_memory_time = time()
                    init_memory_done = True
                    state = 'read_memory'

                elif state == 'read_memory':
                    value_updated = (vfloat32.get_update_time() > init_memory_time + time_margin) and (vint64.get_update_time() >
                                                                                                       init_memory_time + time_margin) and (vbool.get_update_time() > init_memory_time + time_margin)

                    if value_updated:
                        self.assertEqual(vfloat32.get_value(), d2f(3.1415926), 'round=%d' % round_completed)
                        self.assertEqual(vint64.get_value(), 0x123456789abcdef, 'round=%d' % round_completed)
                        self.assertEqual(vbool.get_value(), True, 'round=%d' % round_completed)

                        vfloat32.update_target_value(2.7)
                        vint64.update_target_value(0x1122334455667788)
                        vbool.update_target_value(False)

                        write_time = time()
                        state = 'write_memory'

                    elif time() - init_memory_time > 1:
                        raise Exception('Value did not update')

                elif state == 'write_memory':
                    value_updated = True
                    value_updated = value_updated and (vfloat32.get_last_update_timestamp() is not None) and (
                        vfloat32.get_last_update_timestamp() > write_time)
                    value_updated = value_updated and (vint64.get_last_update_timestamp() is not None) and (
                        vint64.get_last_update_timestamp() > write_time)
                    value_updated = value_updated and (vbool.get_last_update_timestamp() is not None) and (
                        vbool.get_last_update_timestamp() > write_time)

                    if value_updated:
                        self.assertEqual(vfloat32.get_value(), d2f(2.7), 'round=%d' % round_completed)
                        self.assertEqual(vint64.get_value(), 0x1122334455667788, 'round=%d' % round_completed)
                        self.assertEqual(vbool.get_value(), False, 'round=%d' % round_completed)

                        self.assertEqual(self.emulated_device.read_memory(0x10000, 4), struct.pack('<f', d2f(2.7)))
                        self.assertEqual(self.emulated_device.read_memory(0x10010, 8), struct.pack('<q', 0x1122334455667788))
                        self.assertEqual(self.emulated_device.read_memory(0x10020, 1), struct.pack('<b', 0))

                        round_completed += 1
                        state = 'init_memory'

                    elif time() - write_time > 1:
                        raise Exception('Value not written')

            # Make sure we don't disconnect
            if connection_successful:
                self.assertTrue(status == DeviceHandler.ConnectionStatus.CONNECTED_READY)
                self.assertTrue(self.emulated_device.is_connected())

            sleep(0.01)

        self.assertTrue(connection_successful)
        self.assertEqual(round_completed, test_round_to_do)  # Check that we made 5 cycles of value


class TestDeviceHandlerMultipleLink(unittest.TestCase):

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

        # Make sur ewe can work with no link
        self.device_handler.process()
        self.device_handler.process()
        self.device_handler.process()

        self.assertIsNone(self.device_handler.get_comm_link())

        self.device_handler.configure_comm('thread_safe_dummy', {'channel_id': 1})

        # Should behave exactly the same as test_auto_disconnect_if_comm_interrupted
        timeout = 5     # Should take about 2.5 sec to disconnect With heartbeat at every 2 sec
        t1 = time()
        connection_completed = False
        while time() - t1 < timeout:
            self.device_handler.process()
            sleep(0.01)
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
        t1 = time()
        connection_completed = False
        while time() - t1 < timeout:
            self.device_handler.process()
            sleep(0.01)
            status = self.device_handler.get_connection_status()

            if status == DeviceHandler.ConnectionStatus.CONNECTED_READY and connection_completed == False:
                connection_completed = True
                break

        self.assertTrue(connection_completed)
        # self.assertTrue(self.emulated_device1.is_connected())
        self.assertTrue(self.emulated_device2.is_connected())
        self.assertEqual(self.device_handler.get_comm_error_count(), 0)
