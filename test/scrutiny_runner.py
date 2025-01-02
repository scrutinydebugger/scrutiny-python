#    scrutiny_runner.py
#        Custom unit test handlers that extends the default unittest framework
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import unittest
import unittest.case
from typing import Any
from scrutiny.tools import format_eng_unit

class ScrutinyTestResult(unittest.TextTestResult):

    def addDuration(self, test, elapsed):
        setattr(test, '_scrutiny_test_duration', elapsed)
        super().addDuration(test, elapsed)

    def _write_status(self, test, status):
        # Copied from TextTestResult and added the time thing.
        # Super hackyfragilistic
        is_subtest = isinstance(test, unittest.case._SubTest)
        if is_subtest or self._newline:
            if not self._newline:
                self.stream.writeln()
            if is_subtest:
                self.stream.write("  ")
            self.stream.write(self.getDescription(test))
            self.stream.write(" ... ")
        duration = None
        if hasattr(test, '_scrutiny_test_duration'):
            duration = getattr(test, '_scrutiny_test_duration')
        self.stream.write(status)
        if duration is not None and isinstance(duration, (int, float)):
            if duration < 1:
                duration_str = format_eng_unit(duration, decimal=1, unit="s", binary=False) # handle ms, us, ns
            else:
                duration_str = f"{duration:0.1f}s"
            self.stream.write(f" ({duration_str})")
        self.stream.writeln()
        self.stream.flush()
        self._newline = True

class ScrutinyRunner(unittest.TextTestRunner):
    resultclass = ScrutinyTestResult 
