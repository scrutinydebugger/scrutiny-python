#    timer.py
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import time

from typing import Union


class Timer:
    start_time: Union[float, None]

    def __init__(self, timeout: float):
        self.set_timeout(timeout)
        self.start_time = None

    def set_timeout(self, timeout: float) -> None:
        self.timeout = timeout

    def start(self, timeout: float = None) -> None:
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
