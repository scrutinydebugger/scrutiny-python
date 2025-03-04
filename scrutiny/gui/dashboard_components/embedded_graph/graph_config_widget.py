

__all__ = ['GraphConfigWidget', 'GetSignalDatatypeFn', 'ValidationResult']

import math
from dataclasses import dataclass
from PySide6.QtWidgets import QWidget, QFormLayout, QComboBox, QSpinBox, QLabel, QLineEdit, QVBoxLayout, QGroupBox,QTextEdit 
from PySide6.QtGui import QDoubleValidator, QStandardItemModel
from PySide6.QtCore import Qt
from scrutiny.gui.widgets.validable_line_edit import ValidableLineEdit
from scrutiny.gui.widgets.watchable_line_edit import WatchableLineEdit
from scrutiny.gui.core.watchable_registry import WatchableRegistry
from scrutiny.sdk.datalogging import ( TriggerCondition,  SamplingRate, FixedFreqSamplingRate, DataloggingEncoding, XAxisType, 
                                      VariableFreqSamplingRate, DataloggingConfig)
from scrutiny.sdk import EmbeddedDataType, DeviceInfo

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
    _watchable_registry : WatchableRegistry
    _txt_acquisition_name:QLineEdit
    _cmb_sampling_rate:QComboBox
    _spin_decimation:QSpinBox
    _lbl_effective_sampling_rate:QLabel
    _spin_trigger_position:QSpinBox
    _txt_acquisition_timeout:ValidableLineEdit
    _cmb_trigger_condition:QComboBox
    _txtw_trigger_operand1:WatchableLineEdit
    _txtw_trigger_operand2:WatchableLineEdit
    _txtw_trigger_operand3:WatchableLineEdit
    _txt_hold_time_ms:ValidableLineEdit
    _lbl_estimated_duration:QLabel
    _cmb_xaxis_type:QComboBox
    _txtw_xaxis_signal:WatchableLineEdit

    _acquisition_layout:QFormLayout
    _trigger_layout:QFormLayout
    _xaxis_layout:QFormLayout
    _sampling_rate_layout:QFormLayout

    _device_info:Optional[DeviceInfo]


    def __init__(self, parent:QWidget, watchable_registry:WatchableRegistry, get_signal_dtype_fn:Optional[GetSignalDatatypeFn]) -> None:
        super().__init__(parent)
        MAX_HOLD_TIME_MS = math.floor((2**32 - 1) * 1e-7) * 1e3     # 32bits, increment of 100ns
        MAX_TIMEOUT_SEC = math.floor((2**32 - 1) * 1e-7)            # 32bits, increment of 100ns

        layout = QVBoxLayout(self)
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

        self._txt_acquisition_name.setText("Acquisition")

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
        self._cmb_xaxis_type.currentIndexChanged.connect(self._xaxis_type_changed)
        self._spin_decimation.valueChanged.connect(self._decimation_changed_slot)

        self._acquisition_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self._trigger_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self._xaxis_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self._sampling_rate_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        

        def add_row(layout:QFormLayout, txt:str, widget:QWidget, tooltip:Optional[str]=None) -> None:
            label = QLabel(txt)
            if tooltip is not None:
                label.setToolTip(tooltip)
                label.setCursor(Qt.CursorShape.WhatsThisCursor)
            layout.addRow(label, widget)

        # Layouts
        add_row(self._acquisition_layout, "Acquisition name", self._txt_acquisition_name, HelpStrings.ACQUISITION_NAME)
        add_row(self._acquisition_layout, "Acquisition timeout (s)", self._txt_acquisition_timeout, HelpStrings.ACQUISITION_TIMEOUT)
        add_row(self._acquisition_layout, "Estimated duration ", self._lbl_estimated_duration, HelpStrings.ESTIMATED_DURATION)
        
        add_row(self._sampling_rate_layout, "Sampling Rate", self._cmb_sampling_rate, HelpStrings.SAMPLING_RATE)
        add_row(self._sampling_rate_layout, "Decimation", self._spin_decimation, HelpStrings.DECIMATION)
        add_row(self._sampling_rate_layout, "Effective sampling rate", self._lbl_effective_sampling_rate, HelpStrings.EFFECTIVE_SAMPLING_RATE)
        
        add_row(self._xaxis_layout, "X-Axis type", self._cmb_xaxis_type, HelpStrings.XAXIS_TYPE)
        add_row(self._xaxis_layout, "X watchable", self._txtw_xaxis_signal, HelpStrings.XAXIS_SIGNAL)
        
        add_row(self._trigger_layout, "Trigger position (%)", self._spin_trigger_position, HelpStrings.TRIGGER_POSITIION)
        add_row(self._trigger_layout, "Hold Time (ms)", self._txt_hold_time_ms, HelpStrings.HOLD_TIME)
        add_row(self._trigger_layout, "Trigger condition", self._cmb_trigger_condition, HelpStrings.TRIGGER_CONDITION)
        add_row(self._trigger_layout, "  - Operand 1 (x1)", self._txtw_trigger_operand1, HelpStrings.OPERAND1)
        add_row(self._trigger_layout, "  - Operand 2 (x2)", self._txtw_trigger_operand2, HelpStrings.OPERAND2)
        add_row(self._trigger_layout, "  - Operand 3 (x3)", self._txtw_trigger_operand3, HelpStrings.OPERAND3)

        self.update_content()

    def _trigger_condition_changed_slot(self) -> None:
        self.update_content()

    def _sampling_rate_changed_slot(self) -> None:
        self.update_content()
    
    def _xaxis_type_changed(self) -> None:
        self.update_content()
    
    def _decimation_changed_slot(self) -> None:
        self.update_content()

    def get_selected_sampling_rate(self) -> Optional[SamplingRate]:
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
        sampling_rate = self.get_selected_sampling_rate()
        
        if sampling_rate is None:
            return None
        
        if not isinstance(sampling_rate, FixedFreqSamplingRate):
            return None
        
        return sampling_rate.frequency

    def _compute_estimated_duration(self) -> Optional[float]:
        if self._device_info is None:
            return None

        if self._device_info.datalogging_capabilities is None:
            return None
        
        if self._get_signal_dtype_fn is None:
            return None
        
        sampling_rate_hz = self.get_selected_sampling_rate_hz()
        if sampling_rate_hz is None:
            return None
        
        decimation = self._spin_decimation.value()
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
        effective_sampling_rate_label_txt = "N/A"
        estimated_duration_label_txt = "N/A"

        if self._device_info is None:
            self._cmb_sampling_rate.clear()
        else:
            sampling_rate = self.get_selected_sampling_rate()
            if sampling_rate is not None:
                cmb_xaxis_type_model = self._cmb_xaxis_type.model()
                assert isinstance(cmb_xaxis_type_model, QStandardItemModel)
                ideal_time_item = cmb_xaxis_type_model.item(self._cmb_xaxis_type.findData(XAxisType.IdealTime))
                if isinstance(sampling_rate, FixedFreqSamplingRate):
                    ideal_time_item.setEnabled(True)
                else:
                    ideal_time_item.setEnabled(False)
                    if self._cmb_xaxis_type.currentData() == XAxisType.IdealTime:
                        self._cmb_xaxis_type.setCurrentIndex(self._cmb_xaxis_type.findData(XAxisType.MeasuredTime))
                

            sampling_rate_hz = self.get_selected_sampling_rate_hz()
            if sampling_rate_hz is not None:
                decimation = self._spin_decimation.value()
                effective_rate = sampling_rate_hz / decimation
                effective_sampling_rate_label_txt = tools.format_eng_unit(effective_rate, decimal=1, unit="Hz")

                if self._get_signal_dtype_fn is not None:
                    estimated_duration_sec = self._compute_estimated_duration()
                    if estimated_duration_sec is not None:
                        estimated_duration_label_txt = tools.format_eng_unit(estimated_duration_sec, decimal=1, unit="s")

        self._lbl_effective_sampling_rate.setText(effective_sampling_rate_label_txt)
        self._lbl_estimated_duration.setText(estimated_duration_label_txt)

        condition = cast(Optional[TriggerCondition], self._cmb_trigger_condition.currentData())
        if condition is None:
            nb_operand = 0
        else:
            nb_operand = condition.required_operands()
        
        operands = (self._txtw_trigger_operand1, self._txtw_trigger_operand2, self._txtw_trigger_operand3)
        for i in range(len(operands)):
            visible = i <= nb_operand-1
            self._trigger_layout.setRowVisible(operands[i], visible)

        if cast(Optional[XAxisType], self._cmb_xaxis_type.currentData()) == XAxisType.Signal:
            self._xaxis_layout.setRowVisible(self._txtw_xaxis_signal, True)
        else:
            self._xaxis_layout.setRowVisible(self._txtw_xaxis_signal, False)

    def configure_from_device_info(self, device_info:Optional[DeviceInfo]) -> None:
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
            decimation=self._spin_decimation.value(),
            name=acquisition_name,
            timeout=float(self._txt_acquisition_timeout.text())
        )

        trigger_condition = cast(Optional[TriggerCondition], self._cmb_trigger_condition.currentData())
        if trigger_condition is None:
            output.valid = False
            output.error = "Invalid trigger condition"
            return output

        nb_operand = trigger_condition.required_operands()
        txtw_operands = [self._txtw_trigger_operand1,self._txtw_trigger_operand2,self._txtw_trigger_operand3]
        operands:Optional[List[Union[float, str]]] = None
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

        trigger_position_pu = min(max( (self._spin_trigger_position.value())/100, 0), 1)
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


    def get_hold_time_sec(self) -> Optional[float]:
        if not self._txt_hold_time_ms.validate_expect_valid():
            return None
        val = float(self._txt_hold_time_ms.text())/1000
        return val
    
    def get_acquisition_timeout_sec(self) -> Optional[float]:
        if not self._txt_acquisition_timeout.validate_expect_valid():
            return None
        val = float(self._txt_acquisition_timeout.text())
        return val

    def get_txt_acquisition_name(self) -> QLineEdit:
        return self._txt_acquisition_name

    def get_cmb_sampling_rate(self) -> QComboBox:
        return self._cmb_sampling_rate

    def get_spin_decimation(self) -> QSpinBox:
        return self._spin_decimation

    def get_lbl_effective_sampling_rate(self) -> QLabel:
        return self._lbl_effective_sampling_rate

    def get_spin_trigger_position(self) -> QSpinBox:
        return self._spin_trigger_position

    def get_txt_acquisition_timeout(self) -> ValidableLineEdit:
        return self._txt_acquisition_timeout

    def get_cmb_trigger_condition(self) -> QComboBox:
        return self._cmb_trigger_condition

    def get_txtw_trigger_operand1(self) -> WatchableLineEdit:
        return self._txtw_trigger_operand1
    
    def get_txtw_trigger_operand2(self) -> WatchableLineEdit:
        return self._txtw_trigger_operand2
    
    def get_txtw_trigger_operand3(self) -> WatchableLineEdit:
        return self._txtw_trigger_operand3

    def get_txt_hold_time_ms(self) -> ValidableLineEdit:
        return self._txt_hold_time_ms

    def get_lbl_estimated_duration(self) -> QLabel:
        return self._lbl_estimated_duration
    
    def get_cmb_xaxis_type(self) -> QComboBox:
        return self._cmb_xaxis_type
