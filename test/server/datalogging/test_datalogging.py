#    test_datalogging.py
#        Test datalogging features
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2023 Scrutiny Debugger

import scrutiny.server.datalogging.definitions.device as device_datalogging
import scrutiny.server.datalogging.definitions.api as api_datalogging
from scrutiny.core.basic_types import *
from test import ScrutinyUnitTest


class TestDatalogging(ScrutinyUnitTest):

    def test_device_configuration_value_validity(self):
        config = device_datalogging.Configuration()
        with self.assertRaises(ValueError):
            config.decimation = 0
        config.decimation = 1

        with self.assertRaises(ValueError):
            config.trigger_hold_time = -1
        config.trigger_hold_time = 0

        with self.assertRaises(ValueError):
            config.probe_location = -0.1
        with self.assertRaises(ValueError):
            config.probe_location = 1.1
        config.probe_location = 0.5

        with self.assertRaises(ValueError):
            config.timeout = -1
        config.timeout = 0

        with self.assertRaises(ValueError):
            device_datalogging.TriggerCondition(device_datalogging.TriggerConditionID.Equal)  # Missing operand

        with self.assertRaises(ValueError):
            config.trigger_condition = 1

        config.trigger_condition = device_datalogging.TriggerCondition(
            device_datalogging.TriggerConditionID.Equal,
            device_datalogging.RPVOperand(0x1234),
            device_datalogging.LiteralOperand(1)
        )

        config.add_signal(device_datalogging.MemoryLoggableSignal(0x1234, 4))
        config.add_signal(device_datalogging.TimeLoggableSignal())
        config.add_signal(device_datalogging.RPVLoggableSignal(0xabcd))

    def test_server_acquisition_value_validity(self):
        acq = api_datalogging.DataloggingAcquisition("abc")

        axis1 = api_datalogging.AxisDefinition(name='axis1', external_id=0)
        axis2 = api_datalogging.AxisDefinition(name='axis2', external_id=1)

        acq.add_data(api_datalogging.DataSeries([1, 2, 3]), axis1)
        acq.add_data(api_datalogging.DataSeries([4, 5, 6]), axis2)

        with self.assertRaises(ValueError):
            acq.add_data(api_datalogging.DataSeries([1, 2, 3]), api_datalogging.AxisDefinition(name='dup_axis1', external_id=0))


if __name__ == '__main__':
    import unittest
    unittest.main()
