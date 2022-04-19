#    server_tools.py
#        Some tools used by the server
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import time
import math

class Timer:
    def __init__(self, timeout):
        self.set_timeout(timeout)
        self.start_time = None

    def set_timeout(self, timeout):
        self.timeout = timeout

    def start(self, timeout=None):
        if timeout is not None:
            self.set_timeout(timeout)
        self.start_time = time.time()

    def stop(self):
        self.start_time = None

    def elapsed(self):
        if self.start_time is not None:
            return time.time() - self.start_time
        else:
            return 0

    def is_timed_out(self):
        if self.is_stopped() or self.timeout is None:
            return False
        else:
            return self.elapsed() > self.timeout or self.timeout == 0

    def is_stopped(self):
        return self.start_time == None


class Throttler:

    def __init__(self, mean_bitrate = None, window_size_sec = 0.1, time_slot_size =  0.005):
        self.enabled = False
        self.mean_bitrate = mean_bitrate
        self.window_size_sec = window_size_sec
        self.error_reason = ''
        self.time_slot_size = time_slot_size

    def set_bitrate(self, mean_bitrate):
        self.mean_bitrate = mean_bitrate

    def enable(self):
        self.mean_bitrate = float(self.mean_bitrate)
        self.window_size_sec = float(self.window_size_sec)
        self.enabled = True
        self.reset()

    def disable(self):
        self.enabled = False

    def reset(self):
       self.burst_bitcount = []
       self.burst_time = []
       self.bit_total = 0
       self.window_bit_max = self.mean_bitrate*self.window_size_sec

    def update(self):
        if not self.enabled:
           self.reset()
           return 

        t = time.time()

        while len(self.burst_time) > 0:
            t2 = self.burst_time[0]
            if t-t2 > self.window_size_sec:
                self.burst_time.pop(0)
                n_to_remove = self.burst_bitcount.pop(0)
                self.bit_total -= n_to_remove
            else:
                break

    def allowed_bits(self):
        return max(self.window_bit_max - self.bit_total, 0)

    def allowed(self, delta_bandwidth):
        if not self.enabled:
            return True

        return delta_bandwidth <= self.allowed_bits()

        
    def consume_bandwidth(self, delta_bandwidth):
        if self.enabled:
            t = time.time()
            self.bit_total += delta_bandwidth
            if len(self.burst_time) == 0:
                self.burst_time.append(t)
                self.burst_bitcount.append(delta_bandwidth)
            else:
                last_time = self.burst_time[-1]
                if t - last_time > self.time_slot_size:
                    self.burst_time.append(t)
                    self.burst_bitcount.append(delta_bandwidth)
                else:
                    self.burst_bitcount[-1] += delta_bandwidth