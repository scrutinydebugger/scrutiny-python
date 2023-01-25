#    test_datalogging.py
#        Test datalogging features
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2023 Scrutiny Debugger

import scrutiny.server.datalogging.definitions as datalogging
from scrutiny.core.basic_types import *
from test import ScrutinyUnitTest


class TestDatalogging(ScrutinyUnitTest):

    def test_configuration_value_validity(self):
        config = datalogging.Configuration()
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
            datalogging.TriggerCondition(datalogging.TriggerConditionID.Equal)  # Missing operand

        with self.assertRaises(ValueError):
            config.trigger_condition = 1

        config.trigger_condition = datalogging.TriggerCondition(
            datalogging.TriggerConditionID.Equal,
            datalogging.RPVOperand(0x1234),
            datalogging.LiteralOperand(1)
        )

        config.add_signal(datalogging.MemoryLoggableSignal(0x1234, 4))
        config.add_signal(datalogging.TimeLoggableSignal())
        config.add_signal(datalogging.RPVLoggableSignal(0xabcd))


if __name__ == '__main__':
    import unittest
    unittest.main()
