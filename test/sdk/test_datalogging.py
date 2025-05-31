#    test_datalogging.py
#        Test the datalogging features defines in the SDK
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2021 Scrutiny Debugger

import scrutiny.sdk
import scrutiny.sdk.datalogging
sdk = scrutiny.sdk
import unittest
from test import ScrutinyUnitTest


class TestDatalogging(ScrutinyUnitTest):
    def test_acquisition_config(self):
        req = sdk.datalogging.DataloggingConfig(sampling_rate=sdk.datalogging.VariableFreqSamplingRate(2, "foo"))
        self.assertEqual(req._sampling_rate, 2)
        req = sdk.datalogging.DataloggingConfig(sampling_rate=0, decimation=2, name='asd')
        axis1 = req.add_axis('Axis1')
        axis2 = req.add_axis('Axis2')
        req.configure_trigger(sdk.datalogging.TriggerCondition.Equal, [1, '/var/file/my_var'], position=0.75, hold_time=10e-3)
        req.add_signal('/var/file/my_var', axis1, 'foo')
        req.add_signal('/var/file/my_var2', axis1, 'bar')
        req.add_signal('/var/file/my_var3', axis2, 'baz')
        req.configure_xaxis(sdk.datalogging.XAxisType.Indexed)
        req.configure_xaxis(sdk.datalogging.XAxisType.MeasuredTime)
        req.configure_xaxis(sdk.datalogging.XAxisType.IdealTime)
        with self.assertRaises(ValueError):
            req.configure_xaxis(sdk.datalogging.XAxisType.Signal)
        with self.assertRaises(TypeError):
            req.configure_xaxis(sdk.datalogging.XAxisType.Signal, 123)

        req.configure_xaxis(sdk.datalogging.XAxisType.Signal, '/var/file/some_var', name="foobar")

        self.assertEqual(len(req._axes), 2)
        self.assertIn(axis1, req._axes.values())
        self.assertIn(axis2, req._axes.values())

        self.assertEqual(req._trigger_condition, sdk.datalogging.TriggerCondition.Equal)
        self.assertEqual(len(req._trigger_operands), 2)
        self.assertEqual(req._trigger_operands[0], 1)
        self.assertEqual(req._trigger_operands[1], '/var/file/my_var')
        self.assertEqual(req._trigger_position, 0.75)
        self.assertEqual(req._trigger_hold_time, 10e-3)

        self.assertEqual(req._x_axis_type, sdk.datalogging.XAxisType.Signal)
        self.assertEqual(req._x_axis_signal.path, '/var/file/some_var')
        self.assertEqual(req._x_axis_signal.name, "foobar")

        self.assertEqual(req._sampling_rate, 0)
        self.assertEqual(req._decimation, 2)
        self.assertEqual(req._name, "asd")

        for val in [1, [], 0.5]:
            with self.assertRaises(Exception, msg=f"val={val}"):
                sdk.datalogging.DataloggingRequest(sampling_rate=0, decimation=2, name=val)

        for val in [0.5, -1, 0, 'asd', None, [], {}]:
            with self.assertRaises(Exception, msg=f"val={val}"):
                sdk.datalogging.DataloggingRequest(sampling_rate=0, decimation=val, name='asd')

        for val in [0.5, 'asd', None, [], {}]:
            with self.assertRaises(Exception, msg=f"val={val}"):
                sdk.datalogging.DataloggingRequest(sampling_rate=val, decimation=1, name='asd')

        for val in [-0.1, 1, 1.1, 'asd', None, [], {}, True]:
            with self.assertRaises(Exception, msg=f'val={val}'):
                req.configure_trigger(val, [1, '/var/file/my_var'], position=0.5, hold_time=10e-3)

        for val in [-0.1, 1.1, 'asd', None, [], {}, True]:
            with self.assertRaises(Exception, msg=f'val={val}'):
                req.configure_trigger(sdk.datalogging.TriggerCondition.Equal, [1, '/var/file/my_var'], position=val, hold_time=10e-3)

        for val in [-1, 2**32, 'asd', None, [], {}, True]:
            with self.assertRaises(Exception, msg=f'val={val}'):
                req.configure_trigger(sdk.datalogging.TriggerCondition.Equal, [1, '/var/file/my_var'], position=0.5, hold_time=val)

        for val in [1, None, [], {}, True]:
            with self.assertRaises(Exception, msg=f'val={val}'):
                req.add_signal(val, axis1, 'bar')

        for val in ['asd', None, [], {}, True]:
            with self.assertRaises(Exception, msg=f'val={val}'):
                req.add_signal('Asd', val, 'bar')

        for val in [1, [], {}, True]:
            with self.assertRaises(Exception, msg=f'val={val}'):
                req.add_signal('Asd', axis1, val)

        for val in [1, None, [], {}, True]:
            with self.assertRaises(Exception, msg=f'val={val}'):
                req.add_axis(val)


if __name__ == '__main__':
    unittest.main()
