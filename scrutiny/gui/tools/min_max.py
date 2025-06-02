#    min_max.py
#        Helper to compute min/max on a series.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['MinMax']

import math
from scrutiny.tools.typing import *


class MinMax:
    low: float
    high: float

    def __init__(self) -> None:
        self.clear()

    def clear(self) -> None:
        self.low = math.inf
        self.high = -math.inf

    def update(self, v: float) -> None:
        if v > self.high:
            self.high = v
        if v < self.low:
            self.low = v

    def update_from_many(self, s: Sequence[float]) -> None:
        if len(s) > 0:
            self.update_max(max(s))
            self.update_min(min(s))

    def update_min(self, v: float) -> None:
        if v < self.low:
            self.low = v

    def update_max(self, v: float) -> None:
        if v > self.high:
            self.high = v

    def set_min(self, v: float) -> None:
        self.low = v

    def set_max(self, v: float) -> None:
        self.high = v

    def min(self) -> Optional[float]:
        if not math.isfinite(self.low):
            return None
        return self.low

    def max(self) -> Optional[float]:
        if not math.isfinite(self.high):
            return None
        return self.high
