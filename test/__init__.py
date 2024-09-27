#type: ignore
import logging
import unittest
from functools import wraps
from datetime import datetime

from scrutiny.core.datalogging import DataloggingAcquisition, DataSeries, AxisDefinition

__scrutiny__ = True  # we need something to know if we loaded scrutiny "test" module or something else (such as python "test" module)
logger = logging.getLogger('unittest')


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
            self.assertIsInstance(data.series.logged_element, str)
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
        self.assertEqual(a.logged_element, b.logged_element)
        self.assertEqual(a.get_data(), b.get_data())
