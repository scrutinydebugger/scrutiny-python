#    test_datalogging_storage.py
#        Test the datalogging storage
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2023 Scrutiny Debugger

from uuid import uuid4
import random
from test import ScrutinyUnitTest
from scrutiny.server.datalogging.datalogging_storage import DataloggingStorage
from scrutiny.core.datalogging import DataloggingAcquisition, DataSeries, AxisDefinition
from datetime import datetime, timedelta
import time

from typing import *


class TestDataloggingStorage(ScrutinyUnitTest):

    def make_dummy_data(self, datalen: int) -> DataSeries:
        series = DataSeries(name=uuid4().hex, logged_element=uuid4().hex)
        series.set_data([random.random() for i in range(datalen)])
        return series

    def assert_acquisition_valid(self, a: DataloggingAcquisition):
        self.assertIsInstance(a.firmware_id, str)
        self.assertIsInstance(a.reference_id, str)
        self.assertIsInstance(a.acq_time, datetime)
        self.assertIsInstance(a.xdata, DataSeries)
        self.assertIsInstance(a.get_unique_yaxis_list(), list)
        for yaxis in a.get_unique_yaxis_list():
            self.assertIsInstance(yaxis, AxisDefinition)
            self.assertIsInstance(yaxis.name, str)
            self.assertIsInstance(yaxis.external_id, int)

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

        yaxis1 = a.get_unique_yaxis_list()
        yaxis2 = b.get_unique_yaxis_list()
        self.assertEqual(len(yaxis1), len(yaxis2))
        for i in range(len(yaxis1)):
            self.assertEqual(yaxis1[i].name, yaxis2[i].name)

        data1 = a.get_data()
        data2 = b.get_data()
        self.assertEqual(len(data1), len(data2))
        for i in range(len(data1)):
            self.assert_dataseries_identical(data1[i].series, data2[i].series)
            self.assertEqual(data1[i].axis.name, data2[i].axis.name)
            self.assertEqual(data1[i].axis.external_id, data2[i].axis.external_id)

    def assert_dataseries_identical(self, a: DataSeries, b: DataSeries):
        self.assertEqual(a.name, b.name)
        self.assertEqual(a.logged_element, b.logged_element)
        self.assertEqual(a.get_data(), b.get_data())

    def test_read_write(self):
        acq1 = DataloggingAcquisition(firmware_id="firmwareid1", name="Acquisition #1")
        acq2 = DataloggingAcquisition(firmware_id="firmwareid1")
        acq3 = DataloggingAcquisition(firmware_id="firmwareid2")

        axis1 = AxisDefinition("Axis-1", 111)
        axis2 = AxisDefinition("Axis-2", 222)

        acq1.set_xdata(self.make_dummy_data(50))
        acq1.set_trigger_index(25)
        acq1.add_data(self.make_dummy_data(10), axis1)
        acq1.add_data(self.make_dummy_data(15), axis1)
        acq1.add_data(self.make_dummy_data(20), axis2)

        acq2.set_xdata(self.make_dummy_data(50))
        acq2.set_trigger_index(0)
        acq2.add_data(self.make_dummy_data(20), axis2)
        acq2.add_data(self.make_dummy_data(15), axis2)

        acq3.set_xdata(self.make_dummy_data(50))
        acq3.add_data(self.make_dummy_data(10), axis1)
        acq3.add_data(self.make_dummy_data(15), axis2)
        acq3.add_data(self.make_dummy_data(20), axis2)

        with DataloggingStorage.use_temp_storage():
            self.assertEqual(DataloggingStorage.count(), 0)
            self.assertEqual(DataloggingStorage.list(), [])
            DataloggingStorage.save(acq1)
            self.assertEqual(DataloggingStorage.count(), 1)
            DataloggingStorage.save(acq2)
            self.assertEqual(DataloggingStorage.count(), 2)
            DataloggingStorage.save(acq3)
            self.assertEqual(DataloggingStorage.count(), 3)
            acq_list = DataloggingStorage.list()
            self.assertEqual(len(acq_list), 3)
            self.assertIn(acq1.reference_id, acq_list)
            self.assertIn(acq2.reference_id, acq_list)
            self.assertIn(acq3.reference_id, acq_list)

            self.assertEqual(DataloggingStorage.count(firmware_id="firmwareid1"), 2)
            self.assertEqual(DataloggingStorage.count(firmware_id="firmwareid2"), 1)

            acq1_fetched = DataloggingStorage.read(acq1.reference_id)
            acq2_fetched = DataloggingStorage.read(acq2.reference_id)
            acq3_fetched = DataloggingStorage.read(acq3.reference_id)

            self.assert_acquisition_valid(acq1_fetched)
            self.assert_acquisition_valid(acq2_fetched)
            self.assert_acquisition_valid(acq3_fetched)

            self.assert_acquisition_identical(acq1, acq1_fetched)
            self.assert_acquisition_identical(acq2, acq2_fetched)
            self.assert_acquisition_identical(acq3, acq3_fetched)

            self.assertEqual(acq3_fetched.name, None)
            DataloggingStorage.update_acquisition_name(acq3.reference_id, "meow")
            DataloggingStorage.update_axis_name(acq3.reference_id, axis2.external_id, "woof")
            acq3_fetched = DataloggingStorage.read(acq3.reference_id)
            self.assertEqual(acq3_fetched.name, "meow")
            self.assertEqual(acq3_fetched.get_data()[1].axis.name, "woof")
            self.assertEqual(acq3_fetched.get_data()[2].axis.name, "woof")

            DataloggingStorage.delete(acq2.reference_id)

            with self.assertRaises(LookupError):
                DataloggingStorage.read(acq2.reference_id)

            DataloggingStorage.read(acq1.reference_id)
            DataloggingStorage.read(acq3.reference_id)

            self.assertEqual(DataloggingStorage.count(firmware_id='firmwareid1'), 1)
            self.assertEqual(DataloggingStorage.count(firmware_id='firmwareid2'), 1)

            acq_list = DataloggingStorage.list()
            self.assertEqual(len(acq_list), 2)
            self.assertIn(acq1.reference_id, acq_list)
            self.assertIn(acq3.reference_id, acq_list)

            DataloggingStorage.delete(acq1.reference_id)
            DataloggingStorage.delete(acq3.reference_id)

            self.assertEqual(DataloggingStorage.count(), 0)
            self.assertEqual(DataloggingStorage.list(), [])

    def test_bad_reference_id(self):
        with DataloggingStorage.use_temp_storage():
            with self.assertRaises(LookupError):
                DataloggingStorage.update_acquisition_name(
                    reference_id='inexistant_id',
                    name='hello'
                )

            with self.assertRaises(LookupError):
                DataloggingStorage.delete(
                    reference_id='inexistant_id'
                )

            with self.assertRaises(LookupError):
                DataloggingStorage.read(
                    reference_id='inexistant_id'
                )

    def test_read_meta(self):
        with DataloggingStorage.use_temp_storage():
            self.assertIsInstance(DataloggingStorage.get_db_version(), int)
            self.assertIsNone(DataloggingStorage.get_timerange())

            acq1 = DataloggingAcquisition(firmware_id="firmwareid1", name="Acquisition #1")
            axis1 = AxisDefinition("Axis-1", 111)
            acq1.set_xdata(self.make_dummy_data(50))
            acq1.add_data(self.make_dummy_data(10), axis1)
            DataloggingStorage.save(acq1)

            time.sleep(3)

            acq2 = DataloggingAcquisition(firmware_id="firmwareid1", name="Acquisition #1")
            acq2.set_xdata(self.make_dummy_data(50))
            acq2.add_data(self.make_dummy_data(10), axis1)
            DataloggingStorage.save(acq2)

            timerange = DataloggingStorage.get_timerange()
            self.assertIsInstance(timerange, tuple)
            self.assertEqual(len(timerange), 2)
            self.assertIsInstance(timerange[0], datetime)
            self.assertIsInstance(timerange[1], datetime)
            self.assertNotEqual(timerange[0], timerange[1])
            self.assertLessEqual(timerange[1] - timerange[0], timedelta(seconds=10))


if __name__ == '__main__':
    import unittest
    unittest.main()
