#    test_datalogging.py
#        Test the datalogging features from the core module (shared across modules)
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2023 Scrutiny Debugger

from scrutiny.core.datalogging import *
from scrutiny.core.basic_types import WatchableType
from test import ScrutinyUnitTest


class TestDatalogging(ScrutinyUnitTest):
    def test_server_acquisition_value_validity(self):
        acq = DataloggingAcquisition("abc")

        axis1 = AxisDefinition(name='axis1', axis_id=0)
        axis2 = AxisDefinition(name='axis2', axis_id=1)

        watchable1 = LoggedWatchable("/a/b", WatchableType.Variable)
        watchable2 = LoggedWatchable("/a/c", WatchableType.Alias)
        acq.add_data(DataSeries([1, 2, 3], logged_watchable=watchable1), axis1)
        acq.add_data(DataSeries([4, 5, 6], logged_watchable=watchable2), axis2)

        with self.assertRaises(ValueError):
            acq.add_data(DataSeries([1, 2, 3]), AxisDefinition(name='dup_axis1', axis_id=0))
