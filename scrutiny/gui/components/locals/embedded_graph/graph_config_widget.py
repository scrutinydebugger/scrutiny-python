#    graph_config_widget.py
#        A widget that let a user configure a datalogging configuration (except the list of
#        signals). Meant to be used  in the EmbeddedGraph component
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['GraphConfigWidget', 'GetSignalDatatypeFn', 'ValidationResult']

import math
import re

from dataclasses import dataclass
from PySide6.QtWidgets import QWidget, QFormLayout, QComboBox, QSpinBox, QLabel, QLineEdit, QVBoxLayout, QGroupBox, QSizePolicy 
from PySide6.QtGui import QDoubleValidator, QStandardItemModel
from PySide6.QtCore import Qt
from scrutiny.gui.widgets.validable_line_edit import ValidableLineEdit
from scrutiny.gui.widgets.watchable_line_edit import WatchableLineEdit
from scrutiny.gui.core.watchable_registry import WatchableRegistry
from scrutiny.sdk.datalogging import ( TriggerCondition,  SamplingRate, FixedFreqSamplingRate, DataloggingEncoding, XAxisType, 
                                      VariableFreqSamplingRate, DataloggingConfig)
from scrutiny.sdk import EmbeddedDataType, DeviceInfo
from scrutiny.sdk.watchable_handle import WatchableHandle

from scrutiny.tools.typing import *
from scrutiny import tools

GetSignalDatatypeFn = Callable[[], List[EmbeddedDataType]]

@dataclass
class ValidationResult:
    config:Optional[DataloggingConfig]
    valid:bool
    error:Optional[str]

class HelpStrings:
    ACQUISITION_NAME = r"A name used to identify the acquisition in the server database"
    ACQUISITION_TIMEOUT = r"Maximum length of the acquisition in seconds. 0 means no limit"
    ESTIMATED_DURATION = r"Estimation of the length of the acquisition based on the actual configuration. \n Only available with fixed frequency sampling rates"
    SAMPLING_RATE = r"The sampling rate used for datalogging. Maps directly to an embedded loop/task"
    DECIMATION = r"A decimation factor to reduce the effective sampling rate. A factor of N will take 1 sample every N loop iteration"
    EFFECTIVE_SAMPLING_RATE = r"Effective sampling rate. (Sampling rate divided by decimation factor)"
    XAXIS_TYPE = r"""The type of X-Axis.

None: X-Axis will be a incremental index from 0 to N
Ideal Time: A time axis deduced using the effective sampling rate, takes no buffer space
Measured time: A time axis measured by the device, require space in the datalogging buffer (reduce the duration)
Signal: An arbitrary watchable will be used, allow making scatter X-Y plots
"""
    XAXIS_SIGNAL = r"The watchable element to use as a X-Axis. Must be Dragged & dropped from other widgets"
    TRIGGER_POSITIION = r"The position of the trigger event in the acquisition buffer. 0% is leftmost, 50% centers the event. 100% puts the trigger event at the far right"
    HOLD_TIME = r"For how long must the trigger condition evaluates to true to fire the trigger event. Accepts decimal values (resolution 100ns)"
    TRIGGER_CONDITION = r"""The condition that must evaluate to true in order to fire the trigger event
Always True: Evaluates to true at the very first sample. Useful to take an instant graph.

Equal: x1 = x2
NotEqual: x1 != x2
GreaterThan: x1 > x2
GreaterOrEqualThan: x1 >= x2
LessThan: x1 < x2
LessOrEqualThan: x1 <= x2
ChangeMoreThan: |dx1| > |x2| & sign(dx1)=sign(x2)
IsWithin: |x1-x2| < |x3|    
"""
    OPERAND1 = r"Operand x1 for trigger condition. Can be a literal or a watchable dragged & dropped from other widgets"
    OPERAND2 = r"Operand x2 for trigger condition. Can be a literal or a watchable dragged & dropped from other widgets"
    OPERAND3 = r"Operand x3 for trigger condition. Can be a literal or a watchable dragged & dropped from other widgets"

class GraphConfigWidget(QWidget):
    _get_signal_dtype_fn:Optional[GetSignalDatatypeFn]
    """A function that returns the list of signal size. USed to compute the duration estimate"""
    _watchable_registry : WatchableRegistry
    """A reference to the global watchable registry for validation"""
    _txt_acquisition_name:QLineEdit
    """LineEdit for the acquisition name"""
    _cmb_sampling_rate:QComboBox
    """ComboBox : List of sampling rates"""
    _spin_decimation:QSpinBox
    """Spinbox : Decimation factor"""
    _lbl_effective_sampling_rate:QLabel
    """A label that shows the effective sampling rate (sampling_rate/decimation)"""
    _spin_trigger_position:QSpinBox
    """Spingbox : Trigger position from 0 to 100"""
    _txt_acquisition_timeout:ValidableLineEdit
    """LineEdit: Acquisition timeout"""
    _cmb_trigger_condition:QComboBox
    """ComboxBox: The type of trigger condition"""
    _txtw_trigger_operand1:WatchableLineEdit
    """Trigger operand 1"""
    _txtw_trigger_operand2:WatchableLineEdit
    """Trigger operand 2"""
    _txtw_trigger_operand3:WatchableLineEdit
    """Trigger operand 3"""
    _txt_hold_time_ms:ValidableLineEdit
    """The acquisition hold time (in ms)"""
    _lbl_estimated_duration:QLabel
    """Label: Estimated duration based on the signals, the x axis, buffer size and effective sampling rate"""
    _cmb_xaxis_type:QComboBox
    """Type of X-Axis"""
    _txtw_xaxis_signal:WatchableLineEdit
    """A watchable for X-Axis when X-Axis type = Signal"""
    _user_changed_xaxis:bool
    """A flag that latches to True when the user changes the value of the X-Axis type combo box"""

    _acquisition_layout:QFormLayout
    _trigger_layout:QFormLayout
    _xaxis_layout:QFormLayout
    _sampling_rate_layout:QFormLayout

    _device_info:Optional[DeviceInfo]
    """The DeviceInfo struct of the actually connected device. None means no device available"""
    
    AUTONAME_PREFIX = r"Acquisition #"

    def __init__(self, parent:QWidget, watchable_registry:WatchableRegistry, get_signal_dtype_fn:Optional[GetSignalDatatypeFn]) -> None:
        super().__init__(parent)
        MAX_HOLD_TIME_MS = math.floor((2**32 - 1) * 1e-7) * 1e3     # 32bits, increment of 100ns
        MAX_TIMEOUT_SEC = math.floor((2**32 - 1) * 1e-7)            # 32bits, increment of 100ns
        self._user_changed_xaxis = False
        self._user_changed_name_once = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2,0,2,0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        acquisition_container = QGroupBox("Acquisition")
        sampling_rate_container = QGroupBox("Sampling rate")
        xaxis_container = QGroupBox("X-Axis")
        trigger_container = QGroupBox("Trigger")
        layout.addWidget(acquisition_container)
        layout.addWidget(sampling_rate_container)
        layout.addWidget(xaxis_container)
        layout.addWidget(trigger_container)

        self._acquisition_layout = QFormLayout(acquisition_container)
        self._sampling_rate_layout = QFormLayout(sampling_rate_container)
        self._xaxis_layout = QFormLayout(xaxis_container)
        self._trigger_layout = QFormLayout(trigger_container)
        self._device_info = None
        self._get_signal_dtype_fn = get_signal_dtype_fn
        self._watchable_registry = watchable_registry

        # Widgets
        self._txt_acquisition_name = QLineEdit(self)
        self._cmb_sampling_rate = QComboBox(self)
        self._cmb_sampling_rate.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        self._spin_decimation = QSpinBox(self)
        self._lbl_effective_sampling_rate = QLabel(self)
        self._spin_trigger_position = QSpinBox(self)
        self._txt_acquisition_timeout = ValidableLineEdit(
            hard_validator=QDoubleValidator(0,MAX_TIMEOUT_SEC,7),
            parent=self
        )
        self._cmb_trigger_condition = QComboBox(self)
        self._txtw_trigger_operand1 = WatchableLineEdit("", self)
        self._txtw_trigger_operand1.setValidator(QDoubleValidator())
        self._txtw_trigger_operand2 = WatchableLineEdit("", self)
        self._txtw_trigger_operand2.setValidator(QDoubleValidator())
        self._txtw_trigger_operand3 = WatchableLineEdit("", self)
        self._txtw_trigger_operand3.setValidator(QDoubleValidator())
        self._cmb_xaxis_type = QComboBox(self)
        self._txtw_xaxis_signal = WatchableLineEdit("", self)
        self._txtw_xaxis_signal.set_text_mode_enabled(False)    # No literal allowed, just watchables
        
        self._txt_hold_time_ms = ValidableLineEdit(
            hard_validator=QDoubleValidator(0, MAX_HOLD_TIME_MS, 4),
            parent=self
        )
        self._lbl_estimated_duration = QLabel(self)

        self._txt_acquisition_name.setText(self.AUTONAME_PREFIX + "1")
        self._txt_acquisition_name.textEdited.connect(self._acquisition_name_edited_slot)

        self._spin_decimation.setMinimum(1)
        self._spin_decimation.setValue(1)
        self._spin_decimation.setMaximum(255)

        self._spin_trigger_position.setMinimum(0)
        self._spin_trigger_position.setMaximum(100)
        self._spin_trigger_position.setValue(50)


        self._txt_acquisition_timeout.setText("0")
        self._txt_hold_time_ms.setText("0")

        self._cmb_trigger_condition.addItem("Always True", TriggerCondition.AlwaysTrue)
        self._cmb_trigger_condition.addItem("Equal (=)", TriggerCondition.Equal)
        self._cmb_trigger_condition.addItem("Not Equal (!=)", TriggerCondition.NotEqual)
        self._cmb_trigger_condition.addItem("Greater Than (>)", TriggerCondition.GreaterThan)
        self._cmb_trigger_condition.addItem("Greater or Equal (>=)", TriggerCondition.GreaterOrEqualThan)
        self._cmb_trigger_condition.addItem("Less Than (<)", TriggerCondition.LessThan)
        self._cmb_trigger_condition.addItem("Less or Equal (<=)", TriggerCondition.LessOrEqualThan)
        self._cmb_trigger_condition.addItem("Change More Than", TriggerCondition.ChangeMoreThan)
        self._cmb_trigger_condition.addItem("Is Within", TriggerCondition.IsWithin)

        self._cmb_xaxis_type.addItem("None", XAxisType.Indexed)
        self._cmb_xaxis_type.addItem("Ideal Time", XAxisType.IdealTime)
        self._cmb_xaxis_type.addItem("Measured Time", XAxisType.MeasuredTime)
        self._cmb_xaxis_type.addItem("Signal", XAxisType.Signal)

        self._cmb_trigger_condition.setCurrentIndex(self._cmb_trigger_condition.findData(TriggerCondition.AlwaysTrue))
        self._cmb_trigger_condition.currentIndexChanged.connect(self._trigger_condition_changed_slot)
        self._cmb_sampling_rate.currentIndexChanged.connect(self._sampling_rate_changed_slot)
        self._cmb_xaxis_type.currentIndexChanged.connect(self._xaxis_type_changed_slot)
        self._cmb_xaxis_type.activated.connect(self._xaxis_type_activated_slot)
        self._spin_decimation.valueChanged.connect(self._decimation_changed_slot)

        self._acquisition_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self._trigger_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self._xaxis_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self._sampling_rate_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        
        def add_row(layout:QFormLayout, txt:str, widget:QWidget, tooltip:Optional[str]) -> None:
            label = QLabel(txt)
            if tooltip is not None:
                label.setToolTip(tooltip)
                label.setCursor(Qt.CursorShape.WhatsThisCursor)
            layout.addRow(label, widget)

        # Layouts
        add_row(self._acquisition_layout, "Name", self._txt_acquisition_name, HelpStrings.ACQUISITION_NAME)
        add_row(self._acquisition_layout, "Timeout (s)", self._txt_acquisition_timeout, HelpStrings.ACQUISITION_TIMEOUT)
        add_row(self._acquisition_layout, "Duration ", self._lbl_estimated_duration, HelpStrings.ESTIMATED_DURATION)
        
        add_row(self._sampling_rate_layout, "Rate", self._cmb_sampling_rate, HelpStrings.SAMPLING_RATE)
        add_row(self._sampling_rate_layout, "Decimation", self._spin_decimation, HelpStrings.DECIMATION)
        add_row(self._sampling_rate_layout, "Effective rate", self._lbl_effective_sampling_rate, HelpStrings.EFFECTIVE_SAMPLING_RATE)
        
        add_row(self._xaxis_layout, "X-Axis type", self._cmb_xaxis_type, HelpStrings.XAXIS_TYPE)
        add_row(self._xaxis_layout, "X watchable", self._txtw_xaxis_signal, HelpStrings.XAXIS_SIGNAL)
        
        add_row(self._trigger_layout, "Position (%)", self._spin_trigger_position, HelpStrings.TRIGGER_POSITIION)
        add_row(self._trigger_layout, "Hold Time (ms)", self._txt_hold_time_ms, HelpStrings.HOLD_TIME)
        add_row(self._trigger_layout, "Condition", self._cmb_trigger_condition, HelpStrings.TRIGGER_CONDITION)
        add_row(self._trigger_layout, "  - Operand 1 (x1)", self._txtw_trigger_operand1, HelpStrings.OPERAND1)
        add_row(self._trigger_layout, "  - Operand 2 (x2)", self._txtw_trigger_operand2, HelpStrings.OPERAND2)
        add_row(self._trigger_layout, "  - Operand 3 (x3)", self._txtw_trigger_operand3, HelpStrings.OPERAND3)

        widget_order = [self._txt_acquisition_name,
                        self._txt_acquisition_timeout,
                        self._lbl_estimated_duration,
                        self._cmb_sampling_rate,
                        self._spin_decimation,
                        self._lbl_effective_sampling_rate,
                        self._cmb_xaxis_type,
                        self._txtw_xaxis_signal,
                        self._spin_trigger_position,
                        self._txt_hold_time_ms,
                        self._cmb_trigger_condition,
                        self._txtw_trigger_operand1,
                        self._txtw_trigger_operand2,
                        self._txtw_trigger_operand3]

        for i in range(len(widget_order)):
            if i > 0:
                self.setTabOrder(widget_order[i-1], widget_order[i])

        self.update_content()

    def _trigger_condition_changed_slot(self) -> None:
        self.update_content()

    def _sampling_rate_changed_slot(self) -> None:
        self.update_content()

        if self._user_changed_xaxis == False:
            rate = self.get_selected_sampling_rate()
            if isinstance(rate, FixedFreqSamplingRate):
                self.set_axis_type(XAxisType.IdealTime)
            elif isinstance(rate, VariableFreqSamplingRate):
                self.set_axis_type(XAxisType.MeasuredTime)
    
    def _xaxis_type_changed_slot(self) -> None:
        self.update_content()
    
    def _xaxis_type_activated_slot(self) -> None:
        self._user_changed_xaxis = True

    def _decimation_changed_slot(self) -> None:
        self.update_content()

    def _acquisition_name_edited_slot(self) -> None:
        self._user_changed_name_once = True

    def get_selected_sampling_rate(self) -> Optional[SamplingRate]:
        """Return the selected sampling rate. None if none is available"""
        if self._device_info is None:
            return None
        
        if self._device_info.datalogging_capabilities is None:
            return None
        
        selected_identifier = cast(Optional[int], self._cmb_sampling_rate.currentData())
        
        for rate in self._device_info.datalogging_capabilities.sampling_rates:
            if rate.identifier == selected_identifier:
                return  rate

        return None
    
    def get_selected_sampling_rate_hz(self) -> Optional[float]:
        """Return the selected sampling rate frequency in Hz. Return None if no sampling rate is available or if the selected rate has variable frequency"""
        sampling_rate = self.get_selected_sampling_rate()
        
        if sampling_rate is None:
            return None
        
        if not isinstance(sampling_rate, FixedFreqSamplingRate):
            return None
        
        return sampling_rate.frequency

    def _compute_estimated_duration(self) -> Optional[float]:
        """Compute how long the acquisition will be considering:
         - Buffer size
         - Sampling rate
         - Decimation
         - Signals to log
         - X-Axis type
         
         Return a value in seconds. None if the value cannot be computed (value invalid or variable frequency sampling rate)
         """
        if self._device_info is None:
            return None

        if self._device_info.datalogging_capabilities is None:
            return None
        
        if self._get_signal_dtype_fn is None:
            return None
        
        sampling_rate_hz = self.get_selected_sampling_rate_hz()
        if sampling_rate_hz is None:
            return None
        
        decimation = self.get_decimation()
        effective_rate = sampling_rate_hz / decimation
        signal_datatypes = self._get_signal_dtype_fn()
        encoding = self._device_info.datalogging_capabilities.encoding
        buffer_size = self._device_info.datalogging_capabilities.buffer_size
        xaxis_type = cast(Optional[XAxisType], self._cmb_xaxis_type.currentData())
        
        if encoding == DataloggingEncoding.RAW:
            sample_size = sum([dtype.get_size_byte() for dtype in signal_datatypes])
            if xaxis_type == XAxisType.MeasuredTime:
                sample_size += 4    # uint32
            elif xaxis_type == XAxisType.Signal:
                fqn_and_name = self._txtw_xaxis_signal.get_watchable()
                if fqn_and_name is None:
                    return None
                watchable = self._watchable_registry.get_watchable_fqn(fqn_and_name.fqn)
                if watchable is None:
                    return None
                sample_size += watchable.datatype.get_size_byte()
            
            if sample_size == 0:
                return None

            nb_sample_max = buffer_size//sample_size
            duration = nb_sample_max/effective_rate
            try:
                timeout = float(self._txt_acquisition_timeout.text())
                if timeout > 0:
                    duration = min(duration, timeout)
            except Exception:
                pass

            return duration
        else:
            return None


    def update_content(self) -> None:
        """Update the widget based on its content. Show/hide widgets depending on user choice and loaded device capabilities"""
        effective_sampling_rate_label_txt = "N/A"
        estimated_duration_label_txt = "N/A"

        if self._device_info is None:   # No device available
            self._cmb_sampling_rate.clear()
        else:   
            sampling_rate = self.get_selected_sampling_rate()   # Combo box is filled when configure_from_device_info is called
            if sampling_rate is not None:                       # Paranoid check
                cmb_xaxis_type_model = self._cmb_xaxis_type.model()
                assert isinstance(cmb_xaxis_type_model, QStandardItemModel)
                ideal_time_item = cmb_xaxis_type_model.item(self._cmb_xaxis_type.findData(XAxisType.IdealTime))
                if isinstance(sampling_rate, FixedFreqSamplingRate):
                    ideal_time_item.setEnabled(True)    # Ideal time is only possible with a Fixed Freq sampling rate.
                else:
                    ideal_time_item.setEnabled(False)
                    if self._cmb_xaxis_type.currentData() == XAxisType.IdealTime:
                        self._cmb_xaxis_type.setCurrentIndex(self._cmb_xaxis_type.findData(XAxisType.MeasuredTime))
                
            # Compute effective sampling rate and estimated duration
            sampling_rate_hz = self.get_selected_sampling_rate_hz()
            if sampling_rate_hz is not None:
                decimation = self.get_decimation()
                effective_rate = sampling_rate_hz / decimation
                effective_sampling_rate_label_txt = tools.format_eng_unit(effective_rate, decimal=1, unit="Hz")

                if self._get_signal_dtype_fn is not None:
                    estimated_duration_sec = self._compute_estimated_duration()
                    if estimated_duration_sec is not None:
                        estimated_duration_label_txt = "~"+tools.format_eng_unit(estimated_duration_sec, decimal=1, unit="s")

        self._lbl_effective_sampling_rate.setText(effective_sampling_rate_label_txt)
        self._lbl_estimated_duration.setText(estimated_duration_label_txt)
        
        #  Trigger conditon
        condition = cast(Optional[TriggerCondition], self._cmb_trigger_condition.currentData())
        if condition is None:   # Paranoid check
            nb_operand = 0
        else:
            nb_operand = condition.required_operands()  # Will show the textboxes baed on that number
        
        # Makes the operand visible based on the number of operands
        operands = (self._txtw_trigger_operand1, self._txtw_trigger_operand2, self._txtw_trigger_operand3)
        for i in range(len(operands)):
            visible = i <= nb_operand-1
            self._trigger_layout.setRowVisible(operands[i], visible)

        # X-Axis. We want the "Signal" textbox only when type=Signal
        if cast(Optional[XAxisType], self._cmb_xaxis_type.currentData()) == XAxisType.Signal:
            self._xaxis_layout.setRowVisible(self._txtw_xaxis_signal, True)
        else:
            self._xaxis_layout.setRowVisible(self._txtw_xaxis_signal, False)

    def configure_from_device_info(self, device_info:Optional[DeviceInfo]) -> None:
        """Configure the widget for a certain device. None means there is no device avaialble."""
        self._device_info = device_info
        self._cmb_sampling_rate.clear()
        if self._device_info is not None:
            if self._device_info.datalogging_capabilities is not None:
                for rate in self._device_info.datalogging_capabilities.sampling_rates:
                    rate_name = rate.name.strip()
                    if len(rate_name) == 0:
                        rate_name = "<no name>"
                    if isinstance(rate, FixedFreqSamplingRate):
                        freq_str = tools.format_eng_unit(rate.frequency, 1, "Hz")
                        rate_name += f" ({freq_str})"
                    elif isinstance(rate, VariableFreqSamplingRate):
                        rate_name += f" (Variable)"
                    else:
                        raise NotImplementedError("Unsupported sampling rate type")

                    self._cmb_sampling_rate.addItem(rate_name, rate.identifier)

        self.update()

    def validate_and_get_config(self) -> ValidationResult:
        """Validate the user input and return a DataloggingConfiguration is it is valid."""
        output = ValidationResult(config=None, valid=True, error=None)

        current_sampling_rate = self._cmb_sampling_rate.currentData()
        if current_sampling_rate is None:
            output.valid = False
            output.error = "Invalid sampling rate"
            return output
        
        acquisition_name = self._txt_acquisition_name.text().strip()
        if len(acquisition_name) == 0:
            acquisition_name = "<unnamed>"

        acquisition_timeout_sec = self.get_acquisition_timeout_sec()
        if acquisition_timeout_sec is None:
            output.valid = False
            output.error = "Invalid timeout"
            return output
        
        config = DataloggingConfig(
            sampling_rate=current_sampling_rate,
            decimation=self.get_decimation(),
            name=acquisition_name,
            timeout=acquisition_timeout_sec
        )

        trigger_condition = cast(Optional[TriggerCondition], self._cmb_trigger_condition.currentData())
        if trigger_condition is None:
            output.valid = False
            output.error = "Invalid trigger condition"
            return output

        nb_operand = trigger_condition.required_operands()
        txtw_operands = [self._txtw_trigger_operand1,self._txtw_trigger_operand2,self._txtw_trigger_operand3]
        # We don't need WatchableHandle here. need it to please static analysis becuse list of union can't detect overlaps with other list of union

        operands:Optional[List[Union[float, str, WatchableHandle]]] = None      
        if nb_operand > 0:
            operands = []
        for i in range(nb_operand):
            assert operands is not None
            txtw_operand = txtw_operands[i]
            if txtw_operand.is_text_mode():
                try:
                    value = float(txtw_operand.text())
                    operands.append(value)
                except Exception:
                    output.valid = False
                    output.error = f"Invalid trigger condition operand #{i+1}"
                    return output
                
            elif txtw_operand.is_watchable_mode():
                fqn_and_name = txtw_operand.get_watchable()
                if fqn_and_name is None:
                    output.valid = False
                    output.error = f"Invalid trigger condition operand #{i+1}"
                    return output

                if not self._watchable_registry.is_watchable_fqn(fqn_and_name.fqn):
                    output.error = f"Watchable in trigger condition operand #{i+1} is not available"
                    output.valid = False
                    return output

                operands.append(WatchableRegistry.FQN.parse(fqn_and_name.fqn).path)
            else:
                raise NotImplementedError("Unknown mode")

            if not output.valid:
                return output

        hold_time_sec = self.get_hold_time_sec()
        if hold_time_sec is None:
            output.valid = False
            output.error = "Invalid hold time"
            return output

        trigger_position_pu = min(max( (self.get_trigger_position())/100, 0), 1)
        config.configure_trigger(
            condition=trigger_condition,
            hold_time=hold_time_sec,
            operands=operands,
            position=trigger_position_pu
        )

        xaxis_type = cast(Optional[XAxisType], self._cmb_xaxis_type.currentData())
        
        if  xaxis_type == XAxisType.Signal:
            fqn_and_name = self._txtw_xaxis_signal.get_watchable()
            if fqn_and_name is None:
                output.valid = False
                output.error = "Invalid X-Axis signal"
                return output

            if not self._watchable_registry.is_watchable_fqn(fqn_and_name.fqn):
                output.valid = False
                output.error = "X-Axis signal is not available"
                return output
            
            config.configure_xaxis(xaxis_type, signal=self._watchable_registry.FQN.parse(fqn_and_name.fqn).path, name=fqn_and_name.name)
        elif  xaxis_type == XAxisType.Indexed:
            config.configure_xaxis(xaxis_type, name="X-Axis")
        elif  xaxis_type == XAxisType.IdealTime:
            config.configure_xaxis(xaxis_type, name="Time (ideal) [s]")
        elif  xaxis_type == XAxisType.MeasuredTime:
            config.configure_xaxis(xaxis_type, name="Time (measured) [s]")
        else:
            raise NotImplementedError("Unsupported X-Axis type")
        
        output.config = config
        return output

    def validate(self) -> bool:
        result = self.validate_and_get_config()
        return result.valid

    def get_hold_time_millisec(self) -> Optional[float]:
        if not self._txt_hold_time_ms.validate_expect_valid():
            return None
        val = float(self._txt_hold_time_ms.text())
        return val
    
    def get_hold_time_sec(self) -> Optional[float]:
        val = self.get_hold_time_millisec()
        if val is None:
            return None
        return val/1000

    def get_acquisition_timeout_sec(self) -> Optional[float]:
        if not self._txt_acquisition_timeout.validate_expect_valid():
            return None
        val = float(self._txt_acquisition_timeout.text())
        return val
    

    def set_axis_type(self, axis_type:XAxisType) -> None:
        selected_sampling_rate = self.get_selected_sampling_rate()
        if axis_type == XAxisType.IdealTime and (selected_sampling_rate is None or not isinstance(selected_sampling_rate, FixedFreqSamplingRate)):
            raise ValueError("Cannot set X Axis type = IdealTime when the selected sampling rate is not a fixed frequency rate")
        self._cmb_xaxis_type.setCurrentIndex(self._cmb_xaxis_type.findData(axis_type))
        self.update_content()

    def update_autoname(self) -> None:
        if self._user_changed_name_once:
            return
        
        m = re.match(self.AUTONAME_PREFIX + r'(\d+)', self._txt_acquisition_name.text())
        if not m:
            return
        try:
            num = int(m.group(1))
        except ValueError:
            return
        
        self._txt_acquisition_name.setText(self.AUTONAME_PREFIX + str(num+1))

    def get_txt_acquisition_name(self) -> QLineEdit:
        return self._txt_acquisition_name

    def get_cmb_sampling_rate(self) -> QComboBox:
        return self._cmb_sampling_rate

    def get_spin_decimation(self) -> QSpinBox:
        return self._spin_decimation
    
    def get_decimation(self) -> int:
        return self._spin_decimation.value()

    def get_lbl_effective_sampling_rate(self) -> QLabel:
        return self._lbl_effective_sampling_rate

    def get_spin_trigger_position(self) -> QSpinBox:
        return self._spin_trigger_position
    
    def get_trigger_position(self) -> int:
        return min(max( (self._spin_trigger_position.value()), 0), 100)

    def get_txt_acquisition_timeout(self) -> ValidableLineEdit:
        return self._txt_acquisition_timeout

    def get_cmb_trigger_condition(self) -> QComboBox:
        return self._cmb_trigger_condition
    
    def get_selected_trigger_condition(self) -> TriggerCondition:
        return cast(TriggerCondition, self._cmb_trigger_condition.currentData())

    def set_selected_trigger_condition(self, v:TriggerCondition) -> None:
        self._cmb_trigger_condition.setCurrentIndex(self._cmb_trigger_condition.findData(v))

    def get_txtw_trigger_operand1(self) -> WatchableLineEdit:
        return self._txtw_trigger_operand1
    
    def get_txtw_trigger_operand2(self) -> WatchableLineEdit:
        return self._txtw_trigger_operand2
    
    def get_txtw_trigger_operand3(self) -> WatchableLineEdit:
        return self._txtw_trigger_operand3
    
    def get_txtw_xaxis_signal(self) -> WatchableLineEdit:
        return self._txtw_xaxis_signal

    def get_txt_hold_time_ms(self) -> ValidableLineEdit:
        return self._txt_hold_time_ms

    def get_lbl_estimated_duration(self) -> QLabel:
        return self._lbl_estimated_duration
    
    def get_cmb_xaxis_type(self) -> QComboBox:
        return self._cmb_xaxis_type

    def get_selected_xaxis_type(self) -> XAxisType:
        return cast(XAxisType, self._cmb_xaxis_type.currentData())
