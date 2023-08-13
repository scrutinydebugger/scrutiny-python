
import scrutiny.sdk
import scrutiny.sdk.datalogging
sdk = scrutiny.sdk
import unittest
from test import ScrutinyUnitTest


class TestDatalogging(ScrutinyUnitTest):
    def test_acquisition_request(self):
        req = sdk.datalogging.DataloggingRequest(sampling_rate=0, decimation=2, name='asd')
        axis1 = req.add_axis('Axis1')
        axis2 = req.add_axis('Axis2')
        req.configure_trigger(sdk.datalogging.TriggerCondition.Equal, [1, '/var/file/my_var'], position=0.75, hold_time=10e-3)
        req.add_signal('/var/file/my_var', axis1, 'foo')
        req.add_signal('/var/file/my_var2', axis1, 'bar')
        req.add_signal('/var/file/my_var3', axis2, 'baz')
        req.configure_xaxis(sdk.datalogging.XAxisType.MeasuredTime)
        req.configure_xaxis(sdk.datalogging.XAxisType.IdealTime)
        with self.assertRaises(Exception):
            req.configure_xaxis(sdk.datalogging.XAxisType.Signal)
        with self.assertRaises(Exception):
            req.configure_xaxis(sdk.datalogging.XAxisType.Signal, 123)

        req.configure_xaxis(sdk.datalogging.XAxisType.Signal, '/var/file/some_var')


if __name__ == '__main__':
    unittest.main()
