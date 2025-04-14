#    test_embedded_graph.py
#        A test suite for the embedded graph component
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from PySide6.QtGui import QStandardItemModel
from test.gui.base_gui_test import ScrutinyBaseGuiTest
from scrutiny.gui.dashboard_components.embedded_graph.graph_config_widget import GraphConfigWidget
from scrutiny.gui.core.watchable_registry import WatchableRegistry
from scrutiny.sdk import *
from scrutiny.sdk.datalogging import *

from scrutiny.tools.typing import *

class TestEmbeddedGraph(ScrutinyBaseGuiTest):
    def setUp(self):
        super().setUp()

        self.device_with_datalogging =  DeviceInfo(
            session_id="asd",
            device_id="xxx",
            display_name="unit test",
            max_tx_data_size=128,
            max_rx_data_size=128,
            rx_timeout_us=50000,
            heartbeat_timeout=5,
            protocol_major=1,
            protocol_minor=1,
            address_size_bits=32,
            max_bitrate_bps=0,
            forbidden_memory_regions=[],
            readonly_memory_regions=[],
            supported_features=SupportedFeatureMap(memory_write=True,datalogging=True,user_command=False,sixtyfour_bits=True),
            datalogging_capabilities=DataloggingCapabilities(
                encoding=DataloggingEncoding.RAW,
                buffer_size=4096,
                max_nb_signal=32,
                sampling_rates=[
                    FixedFreqSamplingRate(0, "sampling_rate_1", float(15200)),
                    VariableFreqSamplingRate(1, "sampling_rate_2"),
                    VariableFreqSamplingRate(2, ""),
                    FixedFreqSamplingRate(3, "", float(1000)),
                ]
            )
        )

        self.device_no_datalogging =  DeviceInfo(
            session_id="asd",
            device_id="xxx",
            display_name="unit test",
            max_tx_data_size=128,
            max_rx_data_size=128,
            rx_timeout_us=50000,
            heartbeat_timeout=5,
            protocol_major=1,
            protocol_minor=1,
            address_size_bits=32,
            max_bitrate_bps=0,
            forbidden_memory_regions=[],
            readonly_memory_regions=[],
            supported_features=SupportedFeatureMap(memory_write=True,datalogging=True,user_command=False,sixtyfour_bits=True),
            datalogging_capabilities=None
        )

        self.registry = WatchableRegistry()
        self.registry.write_content({
            WatchableType.Alias : {
                '/my_var' : WatchableConfiguration('my_var', WatchableType.Variable, EmbeddedDataType.float32, enum=None)
            },
            WatchableType.RuntimePublishedValue : {
                '/my_rpva' : WatchableConfiguration('my_rpv', WatchableType.RuntimePublishedValue, EmbeddedDataType.float32, enum=None)
            },
            WatchableType.Variable : {
                '/my_alias' : WatchableConfiguration('my_alias', WatchableType.Alias, EmbeddedDataType.float32, enum=None),
            },
        })

        self.signal_types:List[EmbeddedDataType] = []
        self.widget = GraphConfigWidget(parent=None, watchable_registry=self.registry, get_signal_dtype_fn=lambda : self.signal_types)


    def test_graph_config_widget_dynamic_behavior(self) -> None:
        na_string = "N/A"
        self.assertIsNone( self.widget.get_selected_sampling_rate() )
        self.assertEqual( self.widget.get_lbl_effective_sampling_rate().text(), na_string)
        self.assertEqual( self.widget.get_lbl_estimated_duration().text(), na_string)

        self.widget.configure_from_device_info(self.device_with_datalogging)
        self.assertIsNotNone( self.widget.get_selected_sampling_rate() )

        cmb_sampling_rate = self.widget.get_cmb_sampling_rate()
        fixed_freq_identifier = 0
        variable_freq_identifier = 1
        variable_freq_no_name_identifier = 2
        fixed_freq_no_name_identifier = 3
        self.assertIsInstance(self.device_with_datalogging.datalogging_capabilities.sampling_rates[fixed_freq_identifier], FixedFreqSamplingRate)
        self.assertIsInstance(self.device_with_datalogging.datalogging_capabilities.sampling_rates[variable_freq_identifier], VariableFreqSamplingRate)
        self.assertIsInstance(self.device_with_datalogging.datalogging_capabilities.sampling_rates[variable_freq_no_name_identifier], VariableFreqSamplingRate)
        self.assertIsInstance(self.device_with_datalogging.datalogging_capabilities.sampling_rates[fixed_freq_no_name_identifier], FixedFreqSamplingRate)

        self.assertEqual(cmb_sampling_rate.count(), 4)
        # For test simplicity, we store the sampling rate in the order of their identifier. Allow indexing the combobox witht he same variable as the sampling rate
        self.assertEqual(cmb_sampling_rate.itemData(fixed_freq_identifier), fixed_freq_identifier)
        self.assertEqual(cmb_sampling_rate.itemData(variable_freq_identifier), variable_freq_identifier)
        self.assertEqual(cmb_sampling_rate.itemData(variable_freq_no_name_identifier), variable_freq_no_name_identifier)
        self.assertEqual(cmb_sampling_rate.itemData(fixed_freq_no_name_identifier), fixed_freq_no_name_identifier)

        self.assertEqual(cmb_sampling_rate.itemText(fixed_freq_identifier), "sampling_rate_1 (15.2KHz)")
        self.assertEqual(cmb_sampling_rate.itemText(variable_freq_identifier), "sampling_rate_2 (Variable)")
        self.assertEqual(cmb_sampling_rate.itemText(variable_freq_no_name_identifier), "<no name> (Variable)")
        self.assertEqual(cmb_sampling_rate.itemText(fixed_freq_no_name_identifier), "<no name> (1.0KHz)")

        cmb_sampling_rate.setCurrentIndex(fixed_freq_identifier)
        self.widget.update_content()

        cmb_xaxis_type = self.widget.get_cmb_xaxis_type()
        self.assertEqual(cmb_xaxis_type.count(), 4)
        xaxis_ideal_time_index = cmb_xaxis_type.findData(XAxisType.IdealTime)
        xaxis_measured_time_index = cmb_xaxis_type.findData(XAxisType.MeasuredTime)
        xaxis_signal_index = cmb_xaxis_type.findData(XAxisType.Signal)
        xaxis_indexed_index = cmb_xaxis_type.findData(XAxisType.Indexed)

        self.assertCountEqual([0,1,2,3], [xaxis_ideal_time_index, xaxis_measured_time_index, xaxis_signal_index, xaxis_indexed_index])

        ideal_time_item = cast(QStandardItemModel, cmb_xaxis_type.model()).item(xaxis_ideal_time_index)
        self.assertTrue(ideal_time_item.isEnabled())

        cmb_sampling_rate.setCurrentIndex(variable_freq_identifier)
        self.widget.update_content()
        self.assertFalse(ideal_time_item.isEnabled())

        self.signal_types.clear()
        cmb_sampling_rate.setCurrentIndex(variable_freq_identifier)
        self.widget.get_spin_decimation().setValue(1)
        self.widget.update_content()
        self.assertEqual(self.widget.get_lbl_effective_sampling_rate().text(), na_string)
        self.assertEqual(self.widget.get_lbl_estimated_duration().text(), na_string)


        cmb_sampling_rate.setCurrentIndex(fixed_freq_identifier)
        self.widget.update_content()
        self.assertEqual(self.widget.get_lbl_effective_sampling_rate().text(), "15.2KHz")
        self.assertEqual(self.widget.get_lbl_estimated_duration().text(), na_string)

        self.widget.get_spin_decimation().setValue(2)
        self.widget.update_content()
        self.assertEqual(self.widget.get_lbl_effective_sampling_rate().text(), "7.6KHz")
        self.assertEqual(self.widget.get_lbl_estimated_duration().text(), na_string)

        self.widget.get_spin_decimation().setValue(100)
        self.widget.update_content()
        self.assertEqual(self.widget.get_lbl_effective_sampling_rate().text(), "152.0Hz")
        self.assertEqual(self.widget.get_lbl_estimated_duration().text(), na_string)

        self.widget.get_spin_decimation().setValue(1)
        self.signal_types.clear()
        self.signal_types.extend([EmbeddedDataType.uint32, EmbeddedDataType.float32 ])
        self.widget.update_content()
        self.assertNotEqual(self.widget.get_lbl_estimated_duration().text(), na_string)

        cmb_sampling_rate.setCurrentIndex(variable_freq_identifier)
        self.widget.update_content()
        self.assertEqual(self.widget.get_lbl_estimated_duration().text(), na_string)


        
    def test_graph_config_widget_limit_values(self):
        self.widget.configure_from_device_info(self.device_with_datalogging)
        self.assertTrue(self.widget.validate())

        self.widget.get_spin_decimation().setValue(0)
        self.assertEqual(self.widget.get_spin_decimation().value(), 1)
        self.widget.get_spin_decimation().setValue(1000)
        self.assertEqual(self.widget.get_spin_decimation().value(), 255)
        self.widget.get_spin_decimation().setValue(1)

        self.widget.get_spin_trigger_position().setValue(-1)
        self.assertEqual(self.widget.get_spin_trigger_position().value(), 0)
        self.widget.get_spin_trigger_position().setValue(1000)
        self.assertEqual(self.widget.get_spin_trigger_position().value(), 100)
        self.widget.get_spin_trigger_position().setValue(50)

        self.widget.get_txt_hold_time_ms().setText("0")
        self.assertTrue(self.widget.validate())
        self.assertEqual(self.widget.get_hold_time_sec(), 0)
        self.widget.get_txt_hold_time_ms().setText("-1")
        self.assertFalse(self.widget.validate())
        self.assertIsNone(self.widget.get_hold_time_sec())
        self.widget.get_txt_hold_time_ms().setText("100.123")
        self.assertEqual(self.widget.get_hold_time_sec(), 0.100123)
        self.assertTrue(self.widget.validate())
        self.widget.get_txt_hold_time_ms().setText("430000")    # overflow, max is 429 sec
        self.assertFalse(self.widget.validate())
        self.assertIsNone(self.widget.get_hold_time_sec())
        self.widget.get_txt_hold_time_ms().setText("0")


        self.widget.get_txt_acquisition_timeout().setText("0")
        self.assertTrue(self.widget.validate())
        self.assertEqual(self.widget.get_acquisition_timeout_sec(), 0)
        self.widget.get_txt_acquisition_timeout().setText("-1")
        self.assertFalse(self.widget.validate())
        self.assertIsNone(self.widget.get_acquisition_timeout_sec())
        self.widget.get_txt_acquisition_timeout().setText("100.123")
        self.assertEqual(self.widget.get_acquisition_timeout_sec(), 100.123)
        self.assertTrue(self.widget.validate())
        self.widget.get_txt_acquisition_timeout().setText("430000")    # overflow, max is 429 sec
        self.assertFalse(self.widget.validate())
        self.assertIsNone(self.widget.get_acquisition_timeout_sec())
        self.widget.get_txt_acquisition_timeout().setText("0")


        trigger_condition = self.widget.get_cmb_trigger_condition()
        operand1 = self.widget.get_txtw_trigger_operand1()
        operand2 = self.widget.get_txtw_trigger_operand2()
        operand3 = self.widget.get_txtw_trigger_operand3()

        visiblity_map = {
            TriggerCondition.AlwaysTrue : [False, False, False],
            TriggerCondition.Equal : [True, True, False],
            TriggerCondition.NotEqual : [True, True, False],
            TriggerCondition.LessThan : [True, True, False],
            TriggerCondition.LessOrEqualThan : [True, True, False],
            TriggerCondition.GreaterThan : [True, True, False],
            TriggerCondition.GreaterOrEqualThan : [True, True, False],
            TriggerCondition.ChangeMoreThan : [True, True, False],
            TriggerCondition.IsWithin : [True, True, True],
        }

        for condition, visiblity_array in visiblity_map.items():
            trigger_condition.setCurrentIndex(trigger_condition.findData(condition))
            self.widget.update_content()
            self.widget.update()
            self.process_events()
            self.assertEqual(visiblity_array, [operand1.isVisibleTo(self.widget), operand2.isVisibleTo(self.widget), operand3.isVisibleTo(self.widget)], f"condition={condition}")
        
        
        
