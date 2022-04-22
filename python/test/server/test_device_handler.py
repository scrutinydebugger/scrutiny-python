#    test_device_handler.py
#        Test the DeviceHandler that manage the communication with the device at high level.
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import unittest

from scrutiny.server.device.emulated_device import EmulatedDevice
from scrutiny.server.device import DeviceHandler
from scrutiny.server.datastore import Datastore
from time import time, sleep
from scrutiny.server.protocol.commands import DummyCommand
from scrutiny.server.protocol import Request, Response
from test import logger

import signal  # For ctrl+c handling


class TestDeviceHandler(unittest.TestCase):
    def ctrlc_handler(self, signal, frame):
        if self.emulated_device is not None:
            self.emulated_device.stop()
        raise KeyboardInterrupt

    def setUp(self):
        ds = Datastore()
        config = {
            'link_type': 'thread_safe_dummy',
            'link_config': {},
            'response_timeout': 0.25,
            'heartbeat_timeout': 2
        }

        self.device_handler = DeviceHandler(config, ds)
        self.device_handler.init_comm()
        link = self.device_handler.get_comm_link()
        self.emulated_device = EmulatedDevice(link)
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
        self.assertEqual(info.supported_feature_map['memory_read'], self.emulated_device.supported_features['memory_read'])
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
