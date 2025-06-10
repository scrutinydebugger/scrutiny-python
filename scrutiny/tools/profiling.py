#    profiling.py
#        Some tools for profiling the application
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

__all__ = ['VariableRateExponentialAverager']

import time


class VariableRateExponentialAverager:
    """Runs a low pass filter of type exponential averager and adjust the coefficients """

    enabled: bool
    """Enable/disable flag"""
    time_estimation_window: float
    """The minimum width of the time window used to compute an instant input rate used as the filter input"""
    tau: float
    """Time constant of the exponential averager."""
    estimated_value: float
    """The filter output"""
    near_zero: float
    """A non-linear threshold """

    def __init__(self, time_estimation_window: float = 0.1, tau: float = 0.01, near_zero: float = 0):
        self.enabled = False
        self.time_estimation_window = time_estimation_window
        self.tau = tau
        self.near_zero = near_zero
        self.reset()

    def disable(self) -> None:
        """Disable the averager, forcing the output to be 0"""
        self.enabled = False
        self.reset()

    def enable(self) -> None:
        """Enable the averager"""
        if not self.enabled:
            self.reset()
            self.enabled = True

    def is_enabled(self) -> bool:
        return self.enabled

    def reset(self) -> None:
        """Clear the internal states"""
        self.last_process_timestamp = time.perf_counter()
        self.estimated_value = 0
        self.sum_since_last_estimation = 0

    def update(self) -> None:
        """Function to call periodically"""
        if not self.enabled:
            self.reset()
            return

        t = time.perf_counter()
        dt = t - self.last_process_timestamp
        if dt >= self.time_estimation_window:
            self.last_process_timestamp = t        # Sets new timestamp

            instant_bitrate = self.sum_since_last_estimation / dt
            self.sum_since_last_estimation = 0     # Reset the data counter

            # Let's adjust the transfer function tor expect the given time constant
            b = min(1, dt / self.tau)   # Approximation. Exact equation is 1-exp(-dt/tau)
            a = 1 - b
            val = b * instant_bitrate + a * self.estimated_value
            if abs(val) < self.near_zero:
                val = 0
            self.estimated_value = val

    def add_data(self, value: int) -> None:
        """Increase the amount of data measured"""
        if self.enabled:
            self.sum_since_last_estimation += value

    def get_value(self) -> float:
        """Return the averaged value"""
        return self.estimated_value

    def set_value(self, val: float) -> None:
        """Set the output of the filter to an arbitrary value"""
        self.estimated_value = val
