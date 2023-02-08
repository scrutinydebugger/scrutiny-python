#    test_datalogging_manager.py
#        Test the datalogging manager features
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2023 Scrutiny Debugger

import scrutiny.server.datalogging.definitions.api as api_datalogging
import scrutiny.server.datalogging.definitions.device as device_datalogging
from scrutiny.server.datastore.datastore import *
from scrutiny.core.variable import Variable
from scrutiny.core.basic_types import *
from test import ScrutinyUnitTest

from scrutiny.server.datalogging.datalogging_manager import DataloggingManager
from typing import List


class TestDataloggingManager(ScrutinyUnitTest):

    def make_var_entry(self, path: str, address: int, datatype: EmbeddedDataType, endianness: Endianness = Endianness.Little) -> DatastoreVariableEntry:
        v = Variable(path, datatype, [], address, endianness)
        return DatastoreVariableEntry(path, v)

    def make_varbit_entry(self, path: str, address: int, datatype: EmbeddedDataType, bitoffset: int, bitsize: int, endianness: Endianness) -> DatastoreVariableEntry:
        v = Variable(path, datatype, [], address, endianness, bitoffset=bitoffset, bitsize=bitsize)
        return DatastoreVariableEntry(path, v)

    def make_rpv_entry(self, path: str, rpv_id: int, datatype: EmbeddedDataType) -> DatastoreRPVEntry:
        return DatastoreRPVEntry(path, RuntimePublishedValue(rpv_id, datatype))

    def setUp(self):
        self.datastore = Datastore()

        self.var1_u32 = self.make_varbit_entry('/var/abc/var1_u32', 0x100000, EmbeddedDataType.uint32,
                                               bitoffset=9, bitsize=5, endianness=Endianness.Little)
        self.var2_u32 = self.make_varbit_entry('/var/abc/var2_u32', 0x100004,
                                               EmbeddedDataType.uint32, bitoffset=9, bitsize=5, endianness=Endianness.Big)
        self.var3_f64 = self.make_var_entry('/var/abc/var3_f64', 0x100008, EmbeddedDataType.float64)
        self.var4_s16 = self.make_var_entry('/var/abc/var4_s16', 0x100010, EmbeddedDataType.sint16)

        self.rpv1000_bool = self.make_rpv_entry('/rpv/abc/rpv1000_bool', 0x1000, EmbeddedDataType.boolean)
        self.rpv2000_f32 = self.make_rpv_entry('/rpv/abc/rpv2000_f32', 0x2000, EmbeddedDataType.float32)

        self.alias_var1_u32 = DatastoreAliasEntry(
            Alias(
                fullpath='/alias/alias_var1_u32',
                target='/var/abc/var1_u32',
                target_type=EntryType.Var,
                gain=2.0,
                offset=100,
                max=100000,
                min=-200000),
            self.var1_u32)

        self.alias_rpv2000_f32 = DatastoreAliasEntry(
            Alias(
                fullpath='/alias/alias_rpv2000_f32',
                target='/rpv/abc/rpv2000_f32',
                target_type=EntryType.RuntimePublishedValue,
                gain=2.0,
                offset=100,
                max=100000,
                min=-200000),
            self.rpv2000_f32)

        self.alias_var4_s16 = DatastoreAliasEntry(
            Alias(
                fullpath='/alias/alias_var4_s16',
                target='/var/abc/var4_s16',
                target_type=EntryType.Var,
                gain=2.0,
                offset=100,
                max=100000,
                min=-200000),
            self.var4_s16)

        self.datastore.add_entry(self.var1_u32)
        self.datastore.add_entry(self.var2_u32)
        self.datastore.add_entry(self.var3_f64)
        self.datastore.add_entry(self.var4_s16)
        self.datastore.add_entry(self.rpv1000_bool)
        self.datastore.add_entry(self.rpv2000_f32)
        self.datastore.add_entry(self.alias_var1_u32)
        self.datastore.add_entry(self.alias_rpv2000_f32)
        self.datastore.add_entry(self.alias_var4_s16)

    def make_test_request(self, operand_watchable: DatastoreEntry, x_axis_type: api_datalogging.XAxisType, x_axis_entry: Optional[DatastoreEntry] = None) -> api_datalogging.AcquisitionRequest:
        yaxis_list = [
            api_datalogging.AxisDefinition("Axis1"),
            api_datalogging.AxisDefinition("Axis2"),
            api_datalogging.AxisDefinition("Axis3")
        ]

        return api_datalogging.AcquisitionRequest(
            name="some_request",
            decimation=2,
            probe_location=0.25,
            rate_identifier=2,   # Loop ID = 2. Number owned by Device Handler (stubbed here)
            timeout=0,
            trigger_hold_time=0.001,
            trigger_condition=api_datalogging.TriggerCondition(
                condition_id=api_datalogging.TriggerConditionID.GreaterThan,
                operands=[
                    api_datalogging.TriggerConditionOperand(type=api_datalogging.TriggerConditionOperandType.WATCHABLE, value=operand_watchable),
                    api_datalogging.TriggerConditionOperand(type=api_datalogging.TriggerConditionOperandType.LITERAL, value=100)
                ]
            ),
            x_axis_type=x_axis_type,
            x_axis_signal=api_datalogging.SignalDefinition('x-axis', x_axis_entry),
            signals=[
                api_datalogging.SignalDefinitionWithAxis('var1_u32', self.var1_u32, axis=yaxis_list[0]),
                api_datalogging.SignalDefinitionWithAxis('var1_u32', self.var1_u32, axis=yaxis_list[0]),    # Duplicate on purpose
                api_datalogging.SignalDefinitionWithAxis('var2_u32', self.var2_u32, axis=yaxis_list[1]),
                api_datalogging.SignalDefinitionWithAxis('var3_f64', self.var3_f64, axis=yaxis_list[1]),
                api_datalogging.SignalDefinitionWithAxis('rpv1000_bool', self.rpv1000_bool, axis=yaxis_list[2]),
                api_datalogging.SignalDefinitionWithAxis('alias_var1_u32', self.alias_var1_u32, axis=yaxis_list[2]),
                api_datalogging.SignalDefinitionWithAxis('alias_rpv2000_f32', self.alias_rpv2000_f32, axis=yaxis_list[2])
            ]
        )

    def test_convert_to_config(self):
        for i in range(3):
            if i == 0:
                req = self.make_test_request(operand_watchable=self.var1_u32, x_axis_type=api_datalogging.XAxisType.MeasuredTime)
            elif i == 1:
                req = self.make_test_request(operand_watchable=self.rpv1000_bool, x_axis_type=api_datalogging.XAxisType.IdealTime)
            elif i == 2:
                req = self.make_test_request(operand_watchable=self.alias_var1_u32,
                                             x_axis_type=api_datalogging.XAxisType.Signal, x_axis_entry=self.alias_var1_u32)  # X axis will not add a signal
            elif i == 3:
                req = self.make_test_request(operand_watchable=self.alias_rpv2000_f32,
                                             x_axis_type=api_datalogging.XAxisType.Signal, x_axis_entry=self.alias_rpv2000_f32)  # X axis will not add a signal
            elif i == 4:
                req = self.make_test_request(operand_watchable=self.alias_var1_u32,
                                             x_axis_type=api_datalogging.XAxisType.Signal, x_axis_entry=self.alias_var4_s16)  # X axis will add a signal
            else:
                raise NotImplementedError()

            config, signalmap = DataloggingManager.make_device_config_from_request(req)

            self.assertIn(self.var1_u32, signalmap, "i=%d" % i)
            self.assertIn(self.var2_u32, signalmap, "i=%d" % i)
            self.assertIn(self.var3_f64, signalmap, "i=%d" % i)
            self.assertIn(self.rpv1000_bool, signalmap, "i=%d" % i)
            self.assertIn(self.alias_var1_u32, signalmap, "i=%d" % i)
            self.assertIn(self.alias_rpv2000_f32, signalmap, "i=%d" % i)
            if i == 4:
                self.assertIn(self.alias_var4_s16, signalmap)

            self.assertEqual(req.decimation, config.decimation)
            self.assertEqual(req.probe_location, config.probe_location)
            self.assertEqual(req.timeout, config.timeout)
            self.assertEqual(req.trigger_hold_time, config.trigger_hold_time)

            self.assertEqual(req.trigger_condition.condition_id, config.trigger_condition.condition_id)
            self.assertEqual(len(config.trigger_condition.get_operands()), 2)

            operand1 = config.trigger_condition.get_operands()[0]
            operand2 = config.trigger_condition.get_operands()[1]
            assert isinstance(operand2, device_datalogging.LiteralOperand)
            self.assertEqual(operand2.value, 100)

            # 0 is Variable. 2 is Alias that points to variable
            if i in [0, 2]:
                assert isinstance(operand1, device_datalogging.VarBitOperand)
                self.assertEqual(operand1.address, self.var1_u32.get_address())
                self.assertEqual(operand1.datatype, self.var1_u32.get_data_type())
                self.assertEqual(operand1.bitoffset, self.var1_u32.get_bitoffset())
                self.assertEqual(operand1.bitsize, self.var1_u32.get_bitsize())
            elif i in [1, 4]:    # i is RPV
                assert isinstance(operand1, device_datalogging.RPVOperand)
                self.assertEqual(operand1.rpv_id, self.rpv1000_bool.get_rpv().id)
            elif i == 3:    # i is RPV
                assert isinstance(operand1, device_datalogging.RPVOperand)
                self.assertEqual(operand1.rpv_id, self.rpv_entries[1].get_rpv().id)
            else:
                raise NotImplementedError()

            signals = config.get_signals()
            len_by_iter = {
                0: 6,
                1: 5,
                2: 5,
                3: 5,
                4: 6
            }

            self.assertEqual(len(signals), len_by_iter[i], "i=%d" % i)

            assert isinstance(signals[signalmap[self.var1_u32]], device_datalogging.MemoryLoggableSignal)
            assert isinstance(signals[signalmap[self.var2_u32]], device_datalogging.MemoryLoggableSignal)
            assert isinstance(signals[signalmap[self.var3_f64]], device_datalogging.MemoryLoggableSignal)

            self.assertEqual(signals[signalmap[self.var1_u32]].address, 0x100001)  # bitoffset 9 cause next memory cell. (little endian)
            self.assertEqual(signals[signalmap[self.var1_u32]].size, 1)    # bitsize 5 becomes 8bits

            self.assertEqual(signals[signalmap[self.var2_u32]].address, 0x100007)  # bitoffset 9 cause next memory cell. (Big endian) 100004 + 4 - 1
            self.assertEqual(signals[signalmap[self.var2_u32]].size, 1)    # bitsize 5 becomes 8bits

            self.assertEqual(signals[signalmap[self.var3_f64]].address, 0x100008)
            self.assertEqual(signals[signalmap[self.var3_f64]].size, 8)

            assert isinstance(signals[signalmap[self.rpv1000_bool]], device_datalogging.RPVLoggableSignal)
            self.assertEqual(signals[signalmap[self.rpv1000_bool]].rpv_id, 0x1000)

            assert isinstance(signals[signalmap[self.alias_var1_u32]], device_datalogging.MemoryLoggableSignal)
            self.assertEqual(signals[signalmap[self.alias_var1_u32]].address, 0x100001)  # bitoffset 9 cause next memory cell. (little endian)
            self.assertEqual(signals[signalmap[self.alias_var1_u32]].size, 1)    # bitsize 5 becomes 8bits

            assert isinstance(signals[signalmap[self.alias_rpv2000_f32]], device_datalogging.RPVLoggableSignal)
            self.assertEqual(signals[signalmap[self.alias_rpv2000_f32]].rpv_id, 0x2000)

            if i == 0:
                assert isinstance(signals[-1], device_datalogging.TimeLoggableSignal)   # Measured Time cause this to be inserted
            elif i == 4:
                alias = self.alias_var4_s16
                assert isinstance(signals[signalmap[self.alias_var4_s16]], device_datalogging.MemoryLoggableSignal)
                assert isinstance(alias.refentry, DatastoreVariableEntry)
                self.assertEqual(signals[signalmap[self.alias_var4_s16]].address, alias.refentry.get_address())
                self.assertEqual(signals[signalmap[self.alias_var4_s16]].size, alias.refentry.get_data_type().get_size_byte())


if __name__ == '__main__':
    import unittest
    unittest.main()
