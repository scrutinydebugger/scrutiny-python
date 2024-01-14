#    throttler.py
#        Allow to do some throttling to reduce the transmission speed
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import time


class Throttler:
    """
    Class that allows us to do throttling on a given communication channels.
    It measure the bitrate and tells us if we should wait or go ahead when we
    need to send data.

    It works with to low pass filter, one fast to get an instantaneous measurement of the bitrate. 
    One slow to get a long-term (relatively speaking) measurement of the bitrate. We allow data 
    transfer only when both of these filters are below the target.
    """

    MIN_BITRATE = 100   # We can't throttle more than 100bps

    enabled: bool
    mean_bitrate: float     # target mean bitrate
    bitrate_estimation_window: float    # Filters updated at this rate
    slow_tau: float     # Time constant of first IIR filter (slow one)
    fast_tau: float     # Time constant of second IIR filter (fast one)
    last_process_timestamp: float
    estimated_bitrate_slow: float
    estimated_bitrate_fast: float
    consumed_since_last_estimation: int

    def __init__(self, mean_bitrate: float = 0, bitrate_estimation_window: float = 0.1):
        self.enabled = False
        self.mean_bitrate = mean_bitrate
        self.bitrate_estimation_window = bitrate_estimation_window
        # 1 sec time constant, but we can't be smaller than the window  (otherwise unstable)
        self.slow_tau = max(1.0, self.bitrate_estimation_window)
        # 0.05 sec time constant, but we can't be smaller than the window (otherwise unstable)
        self.fast_tau = max(0.05, self.bitrate_estimation_window)
        self.reset()

    def set_bitrate(self, mean_bitrate: float) -> None:
        """ Sets the target mean bitrate to respect"""
        self.mean_bitrate = mean_bitrate

    def enable(self) -> None:
        """ Enable the throttler. Will allow everything when disabled"""
        if self.mean_bitrate > self.MIN_BITRATE:
            self.enabled = True
            self.reset()
            self.mean_bitrate = float(self.mean_bitrate)
        else:
            raise ValueError('Throttler requires a bitrate of at least %dbps. Actual bitrate is %dbps' % (self.MIN_BITRATE, round(self.mean_bitrate)))

    def disable(self) -> None:
        """ Disable the throttler"""
        self.enabled = False

    def is_enabled(self) -> bool:
        """Returns True if the Throttler is enabled"""
        return self.enabled

    def get_bitrate(self) -> float:
        """Return the target average bitrate"""
        return self.mean_bitrate

    def reset(self) -> None:
        """ Sets the throttler to its initial state"""
        self.last_process_timestamp = time.time()
        self.estimated_bitrate_slow = 0
        self.estimated_bitrate_fast = 0
        self.consumed_since_last_estimation = 0

    def process(self) -> None:
        """To be called periodically as fast as possible."""
        if not self.enabled:
            self.reset()
            return

        t = time.time()
        dt = t - self.last_process_timestamp
        if dt > self.bitrate_estimation_window:
            # We need to update the filters, e.g. our estimation of the bitrate
            # The time delta (dT) is variable because of thread resolution. We need to recompute the
            # filters weights every time
            instant_bitrate = self.consumed_since_last_estimation / dt  # Filters inputs

            # Fast filter
            b = min(1, dt / self.fast_tau)
            a = 1 - b
            self.estimated_bitrate_fast = b * instant_bitrate + a * self.estimated_bitrate_fast

            # Slow filter
            b = min(1, dt / self.slow_tau)
            a = 1 - b
            self.estimated_bitrate_slow = b * instant_bitrate + a * self.estimated_bitrate_slow

            # Reset instant measurement
            self.consumed_since_last_estimation = 0     # Reset the data counter
            self.last_process_timestamp = t             # Sets new timestamp

    def get_estimated_bitrate(self) -> float:
        """ Estimated bitrate is the long average. Fast average is only to avoid peak at startup."""
        return self.estimated_bitrate_slow

    def allowed(self, delta_bandwidth: int) -> bool:
        """ Tells if it this chunk of data can be sent right now or we should wait"""

        if not self.enabled:
            return True

        allowed = True
        approx_bitrate = max(self.estimated_bitrate_slow, self.estimated_bitrate_fast)

        # bit/s + bit compared with bit/s. Units doesn't match, this is not a mistake.
        if approx_bitrate + self.consumed_since_last_estimation > self.mean_bitrate:
            allowed = False

        return allowed

    def possible(self, delta_bandwidth: int) -> bool:
        """ Tells if it will be ever possible to send this amount of data in one chunk."""

        if not self.enabled:
            return True

        return self.mean_bitrate > 0  # This was originally designed to prevent burst. It is not needed, but we keep the interface

    def consume_bandwidth(self, delta_bandwidth: int) -> None:
        """ Indicates to the throttler that data has been sent"""
        if self.enabled:
            self.consumed_since_last_estimation += delta_bandwidth
