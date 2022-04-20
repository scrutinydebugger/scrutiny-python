#    test_server_tools.py
#        Test various tools for the Python server application
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import unittest
from scrutiny.server.server_tools import Throttler
import time


class TestThrottler(unittest.TestCase):
    def test_throttler_behavior(self):
        throttler = Throttler(mean_bitrate=1024, window_size_sec=1)
        throttler.enable()
        throttler.process()

        self.assertEqual(throttler.allowed_bits(), 1024)
        throttler.consume_bandwidth(1000)
        self.assertEqual(throttler.allowed_bits(), 24)

        throttler.process()
        time.sleep(0.4)
        throttler.process()

        self.assertEqual(throttler.allowed_bits(), 24)

        time.sleep(0.7)
        throttler.process()
        self.assertEqual(throttler.allowed_bits(), 1024)

        throttler.consume_bandwidth(1024 * 2)
        self.assertEqual(throttler.allowed_bits(), 0)
        time.sleep(0.4)
        throttler.process()
        self.assertEqual(throttler.allowed_bits(), 0)
        time.sleep(0.4)
        throttler.process()
        self.assertEqual(throttler.allowed_bits(), 0)
        time.sleep(0.4)
        throttler.process()
        self.assertEqual(throttler.allowed_bits(), 1024)

        self.assertTrue(throttler.allowed(1024))
        self.assertFalse(throttler.allowed(1025))

    def test_throttler_measurement(self):
        bitrate = 10000
        window_size_sec = 1

        throttler = Throttler(mean_bitrate=bitrate, window_size_sec=window_size_sec)
        throttler.enable()

        runtime = 5
        tstart = time.time()
        time_axis = []
        data_axis = []
        max_write_chunk = bitrate / 10    #
        while time.time() - tstart < runtime:
            throttler.process()
            bitcount = throttler.allowed_bits()
            bitcount = min(max_write_chunk, bitcount)
            throttler.consume_bandwidth(bitcount)
            time_axis.append(time.time())
            data_axis.append(bitcount)
            time.sleep(0.001)

        dt = time_axis[-1] - time_axis[0]
        total = 0
        for x in data_axis:
            total += x

        measured_bitrate = total / dt

        self.assertGreater(measured_bitrate, bitrate * 0.85)
        self.assertLess(measured_bitrate, bitrate * 1.15)

        # Now make sure that the buffer wan'T overloaded
        buffer_estimation = []
        buffer_peak = 0
        for i in range(len(data_axis)):

            if len(buffer_estimation) == 0:
                buffer_estimation.append(data_axis[i])
            else:
                dt = time_axis[i] - time_axis[i - 1]
                buffer_estimation.append(buffer_estimation[-1] + data_axis[i] - bitrate * dt)
                buffer_peak = max(buffer_peak, buffer_estimation[-1])

        self.assertLess(buffer_peak, bitrate / window_size_sec)
