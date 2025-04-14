import logging
import unittest
import unittest.case
from functools import wraps
from datetime import datetime
import time

from scrutiny.core.datalogging import DataloggingAcquisition, DataSeries, AxisDefinition, LoggedWatchable, WatchableType
from scrutiny.core.basic_types import WatchableType
from scrutiny.tools import format_eng_unit

__scrutiny__ = True  # we need something to know if we loaded scrutiny "test" module or something else (such as python "test" module)
logger = logging.getLogger('unittest')


class ScrutinyTestResult(unittest.TextTestResult):

    def startTest(self, test):
        super(unittest.TextTestResult, self).startTest(test)
        if self.showAll:
            self.stream.write(self.getDescription(test))
            self.stream.write(" ... ")
            self.stream.flush()
            self._newline = False

        setattr(test, '_scrutiny_test_start_time', time.perf_counter())
    
    def getDescription(self, test):
        return str(test)
    
    def addSubTest(self, test, subtest, err):
        if err is not None:
            if self.showAll:
                if issubclass(err[0], subtest.failureException):
                    self._write_status(subtest, "FAIL")
                else:
                    self._write_status(subtest, "ERROR")
            elif self.dots:
                if issubclass(err[0], subtest.failureException):
                    self.stream.write('F')
                else:
                    self.stream.write('E')
                self.stream.flush()
        super(unittest.TextTestResult, self).addSubTest(test, subtest, err)

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
        if hasattr(test, '_scrutiny_test_start_time'):
            start_time = getattr(test, '_scrutiny_test_start_time')
            if isinstance(start_time, float):
                duration = time.perf_counter() - start_time
        self.stream.write(status)
        if duration is not None:
            if duration < 1:
                duration_str = format_eng_unit(duration, decimal=1, unit="s", binary=False) # handle ms, us, ns
            else:
                duration_str = f"{duration:0.1f}s"
            self.stream.write(f" ({duration_str})")
        self.stream.writeln()
        self.stream.flush()
        self._newline = True

    def addSuccess(self, test):
        super(unittest.TextTestResult, self).addSuccess(test)
        if self.showAll:
            self._write_status(test, "ok")
        elif self.dots:
            self.stream.write('.')
            self.stream.flush()

    def addError(self, test, err):
        super(unittest.TextTestResult, self).addError(test, err)
        if self.showAll:
            self._write_status(test, "ERROR")
        elif self.dots:
            self.stream.write('E')
            self.stream.flush()

    def addFailure(self, test, err):
        super(unittest.TextTestResult, self).addFailure(test, err)
        if self.showAll:
            self._write_status(test, "FAIL")
        elif self.dots:
            self.stream.write('F')
            self.stream.flush()

    def addSkip(self, test, reason):
        super(unittest.TextTestResult, self).addSkip(test, reason)
        if self.showAll:
            self._write_status(test, "skipped {0!r}".format(reason))
        elif self.dots:
            self.stream.write("s")
            self.stream.flush()

    def addExpectedFailure(self, test, err):
        super(unittest.TextTestResult, self).addExpectedFailure(test, err)
        if self.showAll:
            self.stream.writeln("expected failure")
            self.stream.flush()
        elif self.dots:
            self.stream.write("x")
            self.stream.flush()

    def addUnexpectedSuccess(self, test):
        super(unittest.TextTestResult, self).addUnexpectedSuccess(test)
        if self.showAll:
            self.stream.writeln("unexpected success")
            self.stream.flush()
        elif self.dots:
            self.stream.write("u")
            self.stream.flush()

class ScrutinyRunner(unittest.TextTestRunner):
    resultclass = ScrutinyTestResult 

class SkipOnException:
    def __init__(self, exception, msg=""):
        self.exception = exception
        self.msg = msg

    def __call__(self, f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except self.exception as e:
                raise unittest.SkipTest("%s. %s" % (self.msg, str(e)))
        return wrapper


class PrintableBytes(bytes):
    def __repr__(self) -> str:
        return 'bytes(' + self.hex() + ')'


class PrintableByteArray(bytearray):
    def __repr__(self) -> str:
        return 'bytearray(' + bytes(self).hex() + ')'


class ScrutinyUnitTest(unittest.TestCase):

    def assertEqual(self, v1, v2, *args, **kwargs):
        if isinstance(v1, bytes) and isinstance(v2, bytes):
            super().assertEqual(PrintableBytes(v1), PrintableBytes(v2), *args, **kwargs)
        elif isinstance(v1, bytearray) and isinstance(v2, bytearray):
            super().assertEqual(PrintableByteArray(v1), PrintableByteArray(v2), *args, **kwargs)
        else:
            super().assertEqual(v1, v2, *args, **kwargs)

    def assertNotEqual(self, v1, v2, *args, **kwargs):
        if isinstance(v1, bytes) and isinstance(v2, bytes):
            super().assertNotEqual(PrintableBytes(v1), PrintableBytes(v2), *args, **kwargs)
        elif isinstance(v1, bytearray) and isinstance(v2, bytearray):
            super().assertEqual(PrintableByteArray(v1), PrintableByteArray(v2), *args, **kwargs)
        else:
            super().assertNotEqual(v1, v2, *args, **kwargs)

    def assert_acquisition_valid(self, a: DataloggingAcquisition):
        self.assertIsInstance(a.firmware_id, str)
        self.assertIsInstance(a.reference_id, str)
        self.assertIsInstance(a.acq_time, datetime)
        self.assertIsInstance(a.xdata, DataSeries)
        self.assertIsInstance(a.firmware_name, (str, type(None)))
        self.assertIsInstance(a.get_unique_yaxis_list(), list)
        for yaxis in a.get_unique_yaxis_list():
            self.assertIsInstance(yaxis, AxisDefinition)
            self.assertIsInstance(yaxis.name, str)
            self.assertIsInstance(yaxis.axis_id, int)

        self.assertIsInstance(a.get_data(), list)
        for data in a.get_data():
            self.assertIsInstance(data.series, DataSeries)
            self.assertIsInstance(data.series.name, str)
            if data.series.logged_watchable is not None:
                self.assertIsInstance(data.series.logged_watchable, LoggedWatchable)
                self.assertIsInstance(data.series.logged_watchable.path, str)
                self.assertIsInstance(data.series.logged_watchable.type, WatchableType)
            self.assertIsInstance(data.axis, AxisDefinition)

    def assert_acquisition_identical(self, a: DataloggingAcquisition, b: DataloggingAcquisition):
        self.assertEqual(a.name, b.name)
        self.assertEqual(a.firmware_id, b.firmware_id)
        self.assertEqual(a.reference_id, b.reference_id)
        self.assertLess((a.acq_time - b.acq_time).total_seconds(), 1)
        self.assertEqual(a.trigger_index, b.trigger_index)
        self.assertEqual(a.firmware_name, b.firmware_name)

        yaxis1 = a.get_unique_yaxis_list()
        yaxis2 = b.get_unique_yaxis_list()
        self.assertCountEqual(yaxis1, yaxis2)

        data1 = a.get_data()
        data2 = b.get_data()
        self.assertEqual(len(data1), len(data2))
        for i in range(len(data1)):
            self.assert_dataseries_identical(data1[i].series, data2[i].series)
            self.assertEqual(data1[i].axis.name, data2[i].axis.name)
            self.assertEqual(data1[i].axis.axis_id, data2[i].axis.axis_id)

    def assert_dataseries_identical(self, a: DataSeries, b: DataSeries):
        self.assertEqual(a.name, b.name)
        self.assertEqual(a.logged_watchable, b.logged_watchable)
        self.assertEqual(a.get_data(), b.get_data())
