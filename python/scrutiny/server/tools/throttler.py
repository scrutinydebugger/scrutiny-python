#    throttler.py
#        Allow to do some throttling to reduce the transmission speed
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import time
import math


class Throttler:

    MIN_BITRATE = 100

    def __init__(self, mean_bitrate=0, bitrate_estimation_window=0.1):
        self.enabled = False
        self.mean_bitrate = mean_bitrate
        self.bitrate_estimation_window = bitrate_estimation_window
        self.slow_tau = max(1.0, self.bitrate_estimation_window)
        self.fast_tau = max(0.05, self.bitrate_estimation_window)
        self.reset()

    def set_bitrate(self, mean_bitrate):
        self.mean_bitrate = mean_bitrate

    def enable(self):
        if self.mean_bitrate > self.MIN_BITRATE:
            self.enabled = True
            self.reset()
            self.mean_bitrate = float(self.mean_bitrate)
        else:
            raise ValueError('Throttler requires a bitrate of at least %bps. Actual bitrate is %dbps' % (self.MIN_BITRATE, round(self.mean_bitrate)))

    def disable(self):
        self.enabled = False

    def is_enabled(self):
        return self.enabled

    def get_bitrate(self):
        return self.mean_bitrate

    def reset(self):
        self.last_process_timestamp = time.time()
        self.estimated_bitrate_slow = 0
        self.estimated_bitrate_fast = 0
        self.consumed_since_last_estimation = 0

    def process(self):
        if not self.enabled:
            self.reset()
            return

        t = time.time()
        dt = t - self.last_process_timestamp
        if dt > self.bitrate_estimation_window:
            instant_bitrate = self.consumed_since_last_estimation / dt

            b = min(1, dt / self.fast_tau)
            a = 1 - b
            self.estimated_bitrate_fast = b * instant_bitrate + a * self.estimated_bitrate_fast

            b = min(1, dt / self.slow_tau)
            a = 1 - b
            self.estimated_bitrate_slow = b * instant_bitrate + a * self.estimated_bitrate_slow
            self.consumed_since_last_estimation = 0
            self.last_process_timestamp = t

    def get_estimated_bitrate(self):
        return self.estimated_bitrate_slow

    def allowed(self, delta_bandwidth):
        """
        Tells if it this chunk of data can be sent right now or we should wait
        """
        if not self.enabled:
            return True

        # return self.estimated_bitrate_fast < self.mean_bitrate
        return max(self.estimated_bitrate_slow, self.estimated_bitrate_fast) < self.mean_bitrate

    def possible(self, delta_bandwidth):
        """
        Tells if it will be ever possible to send this amount of data in one chunk.
        """
        if not self.enabled:
            return True

        return self.mean_bitrate > 0  # This was originally designed to prevent burst. It is not dneeded, but we keep the interface

    def consume_bandwidth(self, delta_bandwidth):
        if self.enabled:
            self.consumed_since_last_estimation += delta_bandwidth
