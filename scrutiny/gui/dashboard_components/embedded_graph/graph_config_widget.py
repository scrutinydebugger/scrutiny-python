

__all__ = ['GraphConfigWidget', 'GetSignalDatatypeFn']

import math

from PySide6.QtWidgets import QWidget, QFormLayout, QComboBox, QSpinBox, QLabel, QLineEdit
from PySide6.QtGui import QDoubleValidator, QStandardItemModel
from scrutiny.gui.widgets.validable_line_edit import ValidableLineEdit
from scrutiny.gui.tools.validators import NotEmptyValidator
from scrutiny.sdk.datalogging import ( TriggerCondition, DataloggingCapabilities, 
                                      SamplingRate, FixedFreqSamplingRate, DataloggingEncoding, XAxisType, VariableFreqSamplingRate)
from scrutiny.sdk import EmbeddedDataType, DeviceInfo

from scrutiny.tools.typing import *
from scrutiny import tools

GetSignalDatatypeFn = Callable[[], List[EmbeddedDataType]]

class GraphConfigWidget(QWidget):
    _get_signal_dtype_fn:Optional[GetSignalDatatypeFn]
    _txt_acquisition_name:QLineEdit
    _cmb_sampling_rate:QComboBox
    _spin_decimation:QSpinBox
    _lbl_effective_sampling_rate:QLabel
    _spin_trigger_position:QSpinBox
    _txt_acquisition_timeout:ValidableLineEdit
    _cmb_trigger_condition:QComboBox
    _txt_hold_time_ms:ValidableLineEdit
    _lbl_estimated_duration:QLabel

    _device_info:Optional[DeviceInfo]


    def __init__(self, parent:QWidget, get_signal_dtype_fn:Optional[GetSignalDatatypeFn]) -> None:
        super().__init__(parent)
        MAX_HOLD_TIME_MS = math.floor((2**32 - 1) * 1e-7) * 1e3     # 32bits, increment of 100ns
        MAX_TIMEOUT_SEC = math.floor((2**32 - 1) * 1e-7)            # 32bits, increment of 100ns

        layout = QFormLayout(self)
        self._device_info = None
        self._get_signal_dtype_fn = get_signal_dtype_fn

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
        self._cmb_xaxis_type = QComboBox(self)
        
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
        self._cmb_trigger_condition.addItem("Less Than (<)", TriggerCondition.GreaterThan)
        self._cmb_trigger_condition.addItem("Less or Equal (<=)", TriggerCondition.GreaterOrEqualThan)
        self._cmb_trigger_condition.addItem("Change More Than", TriggerCondition.ChangeMoreThan)
        self._cmb_trigger_condition.addItem("Is Within", TriggerCondition.IsWithin)

        self._cmb_xaxis_type.addItem("Ideal Time", XAxisType.IdealTime)
        self._cmb_xaxis_type.addItem("Measured Time", XAxisType.MeasuredTime)
        self._cmb_xaxis_type.addItem("Signal", XAxisType.Signal)

        self._cmb_trigger_condition.setCurrentIndex(self._cmb_trigger_condition.findData(TriggerCondition.AlwaysTrue))
        self._cmb_trigger_condition.currentIndexChanged.connect(self._trigger_condition_changed_slot)
        self._cmb_sampling_rate.currentIndexChanged.connect(self._sampling_rate_changed_slot)
        self._cmb_xaxis_type.currentIndexChanged.connect(self._xaxis_type_changed)
        self._spin_decimation.valueChanged.connect(self._decimation_changed_slot)

        layout.addRow("Acquisition name", self._txt_acquisition_name)
        layout.addRow("Sampling Rate", self._cmb_sampling_rate)
        layout.addRow("Decimation", self._spin_decimation)
        layout.addRow("Effective sampling rate", self._lbl_effective_sampling_rate)
        layout.addRow("Trigger position (%)", self._spin_trigger_position)
        layout.addRow("Acquisition timeout (s)", self._txt_acquisition_timeout)
        layout.addRow("X-Axis type", self._cmb_xaxis_type)
        layout.addRow("Trigger condition", self._cmb_trigger_condition)
        layout.addRow("Hold Time (ms)", self._txt_hold_time_ms)
        layout.addRow("Estimated duration ", self._lbl_estimated_duration)

        self.update_content()

    def _trigger_condition_changed_slot(self) -> None:
        self.update_content()

    def _sampling_rate_changed_slot(self) -> None:
        self.update_content()
    
    def _xaxis_type_changed(self) -> None:
        self.update_content()
    
    def _decimation_changed_slot(self) -> None:
        self.update_content()

    def _get_selected_sampling_rate(self) -> Optional[SamplingRate]:
        if self._device_info is None:
            return None
        
        if self._device_info.datalogging_capabilities is None:
            return None
        
        selected_identifier = self._cmb_sampling_rate.currentData()
        
        for rate in self._device_info.datalogging_capabilities.sampling_rates:
            if rate.identifier == selected_identifier:
                return  rate

        return None
    
    def _get_selected_sampling_rate_hz(self) -> Optional[float]:
        sampling_rate = self._get_selected_sampling_rate()
        
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
        
        sampling_rate_hz = self._get_selected_sampling_rate_hz()
        if sampling_rate_hz is None:
            return None
        
        decimation = self._spin_decimation.value()
        effective_rate = sampling_rate_hz / decimation
        signal_datatypes = self._get_signal_dtype_fn()
        encoding = self._device_info.datalogging_capabilities.encoding
        buffer_size = self._device_info.datalogging_capabilities.buffer_size
        xaxis_type = self._cmb_xaxis_type.currentData()
        
        if encoding == DataloggingEncoding.RAW:
            sample_size = sum([dtype.get_size_byte() for dtype in signal_datatypes])
            if xaxis_type == XAxisType.MeasuredTime:
                sample_size += 4    # unit32
            elif xaxis_type == XAxisType.Signal:
                pass        # TODO
            
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
            sampling_rate = self._get_selected_sampling_rate()
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
                

            sampling_rate_hz = self._get_selected_sampling_rate_hz()
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

    def validate(self) -> bool:
        valid = True
        if len(self._txt_acquisition_timeout.text()) == 0:
            self._txt_acquisition_timeout.setText("0")
        if not self._txt_acquisition_timeout.validate_expect_valid():
            valid = False
        
        if len(self._txt_hold_time_ms.text()) == 0:
            self._txt_hold_time_ms.setText("0")
        if not self._txt_hold_time_ms.validate_expect_valid():
            valid = False

        return valid
