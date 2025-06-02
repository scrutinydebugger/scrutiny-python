#    timebase.py
#        A generic timebase object that can be used to follow relative time interval and map
#        them to real datetime
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['RelativeTimebase']

import time
from datetime import datetime, timedelta
from scrutiny.tools.typing import *


class RelativeTimebase:
    _launch_ref_ns: int
    _launch_dt: datetime

    def __init__(self) -> None:
        self.set_zero_now()

    def set_zero_now(self) -> None:
        self._launch_ref_ns = time.perf_counter_ns()
        self._launch_dt = datetime.now()

    def set_zero_to(self, timestamp: float) -> None:
        self._launch_ref_ns = time.perf_counter_ns()
        self._launch_dt = datetime.fromtimestamp(timestamp)

    def get_zero_timestamp(self) -> float:
        return self.milli_to_dt(0).timestamp()

    def get_nano(self) -> int:
        return time.perf_counter_ns() - self._launch_ref_ns

    def get_micro(self) -> float:
        return float(self.get_nano()) / 1000.0

    def get_milli(self) -> float:
        return float(self.get_nano()) / 1000000.0

    def get_sec(self) -> float:
        return float(self.get_nano()) / 1000000000.0

    def sec_to_dt(self, sec: Union[float, int]) -> datetime:
        # We lose fractions of microseconds here.
        return self._launch_dt + timedelta(seconds=float(sec))

    def milli_to_dt(self, milli: Union[float, int]) -> datetime:
        # We lose fractions of microseconds here.
        return self._launch_dt + timedelta(milliseconds=float(milli))

    def micro_to_dt(self, micro: Union[float, int]) -> datetime:
        # We lose fractions of microseconds here.
        return self._launch_dt + timedelta(milliseconds=float(micro) / 1000.0)

    def nano_to_dt(self, nano: Union[float, int]) -> datetime:
        # We lose fractions of microseconds here.
        return self._launch_dt + timedelta(milliseconds=float(nano) / 1000000.0)

    def dt_to_nano(self, dt: datetime) -> int:
        td = dt - self._launch_dt
        return int(td.total_seconds() * 1e9)

    def dt_to_micro(self, dt: datetime) -> float:
        td = dt - self._launch_dt
        return round(td.total_seconds() * 1e6)

    def dt_to_milli(self, dt: datetime) -> float:
        td = dt - self._launch_dt
        return td.total_seconds() * 1e3

    def dt_to_sec(self, dt: datetime) -> float:
        td = dt - self._launch_dt
        return td.total_seconds()
