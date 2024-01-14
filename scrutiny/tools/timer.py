#    timer.py
#        Minimalist class to make measurement of time easier.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import time

from typing import Union, Optional


class Timer:
    """
    Class to make periodic task or timeout easier to manage.
    """
    start_time: Union[float, None]

    def __init__(self, timeout: float) -> None:
        self.set_timeout(timeout)
        self.start_time = None

    def set_timeout(self, timeout: float) -> None:
        self.timeout = timeout

    def start(self, timeout: Optional[float] = None) -> None:
        if timeout is not None:
            self.set_timeout(timeout)
        self.start_time = time.time()

    def stop(self) -> None:
        self.start_time = None

    def elapsed(self) -> float:
        if self.start_time is not None:
            return time.time() - self.start_time
        else:
            return 0

    def is_timed_out(self) -> bool:
        if self.is_stopped() or self.timeout is None:
            return False
        else:
            return self.elapsed() > self.timeout or self.timeout == 0

    def is_stopped(self) -> bool:
        return self.start_time == None
