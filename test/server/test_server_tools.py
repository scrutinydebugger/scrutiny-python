#    test_server_tools.py
#        Test various tools for the Python server application
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import unittest
from scrutiny.server.tools import Throttler
import time
import logging
import math
from test import logger


class TestThrottler(unittest.TestCase):

    def test_throttler_measurement(self):
        bitrate = 5000
        throttler = Throttler()
        throttler.set_bitrate(bitrate)
        throttler.enable()

        runtime = 5
        tstart = time.time()
        time_axis = []
        data_axis = []
        write_chunk = bitrate / 30    # Keep smaller than 60 because of thread resolution of 16ms
        while time.time() - tstart < runtime:
            throttler.process()
            if throttler.allowed(write_chunk):
                throttler.consume_bandwidth(write_chunk)
                time_axis.append(time.time())
                data_axis.append(write_chunk)
            time.sleep(0.001)

        dt = time_axis[-1] - time_axis[0]
        total = 0
        for x in data_axis:
            total += x

        measured_bitrate = total / dt
        logger.info('Measured bitrate = %0.2fkbps. Target = %0.2fkbps' % (measured_bitrate / 1000.0, bitrate / 1000.0))
        self.assertGreater(measured_bitrate, bitrate * 0.8)
        self.assertLess(measured_bitrate, bitrate * 1.2)

        # Now make sure that the buffer won't be overloaded
        buffer_estimation = []
        buffer_peak = 0
        for i in range(len(data_axis)):

            if len(buffer_estimation) == 0:
                buffer_estimation.append(data_axis[i])
            else:
                dt = time_axis[i] - time_axis[i - 1]
                buffer_estimation.append(buffer_estimation[-1] + data_axis[i] - bitrate * dt)
                buffer_peak = max(buffer_peak, buffer_estimation[-1])

        logger.info('Maximum buffer peak = %dbits' % (math.ceil(buffer_peak)))
