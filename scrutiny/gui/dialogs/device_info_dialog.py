#    device_info_dialog.py
#        A dialog to visualize the device information downloaded after a device has connected.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

__all__ = ['DeviceInfoDialog']

from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QWidget, QVBoxLayout, QGroupBox, QGridLayout
from PySide6.QtCore import Qt

from scrutiny.tools.typing import *
from scrutiny.sdk import DeviceInfo, SupportedFeatureMap, MemoryRegion, SamplingRate, FixedFreqSamplingRate, VariableFreqSamplingRate


def _configure_property_label(label: QLabel, has_tooltip: bool) -> None:
    if has_tooltip:
        label.setCursor(Qt.CursorShape.WhatsThisCursor)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)


def _configure_value_label(label: QLabel) -> None:
    label.setCursor(Qt.CursorShape.IBeamCursor)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)


class SupportedFeatureList(QWidget):
    """A widget to display the device supported features as a list with a Yes/No flag next to it"""

    def __init__(self, features: SupportedFeatureMap):
        super().__init__()
        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        feature_list = [
            ("Memory write", features.memory_write, "Allow writing memory"),
            ("Datalogging", features.datalogging, "The device is able make data acquisitions for embedded graphs"),
            ("64 bits", features.sixtyfour_bits, "The device is able use 64bits value as RPVs and datalogger operands."),
            ("User command", features.user_command, "The device has a callback registered for the UserCommand request. (Custom extension of the protocol)")
        ]
        for feature in feature_list:
            title, enable, tooltip = feature
            if enable:
                value_label = QLabel("Yes")
            else:
                value_label = QLabel("No")

            value_label.setProperty("feature_enable", enable)
            feature_label = QLabel(f"- {title} :")
            feature_label.setToolTip(tooltip)
            _configure_property_label(feature_label, has_tooltip=True)
            _configure_value_label(value_label)
            layout.addRow(feature_label, value_label)

        layout.setSpacing(1)


class MemoryRegionList(QWidget):
    """A widget to display a list of memory regions. Used to print the list of read-only and forbidden regions"""

    def __init__(self, regions: List[MemoryRegion], address_size_bits: int = 64):
        super().__init__()
        address_size = address_size_bits // 8
        if address_size % 2 == 1:
            address_size += 1

        def make_label(region: MemoryRegion) -> QLabel:
            format_string = f"0x%0{address_size}X"
            s1 = format_string % region.start
            s2 = format_string % region.end
            label = QLabel(f"- {s1}-{s2}")
            _configure_value_label(label)
            return label

        layout = QVBoxLayout(self)
        if len(regions) == 0:
            label = QLabel("None")
            _configure_value_label(label)
            layout.addWidget(label)
        else:
            for region in regions:
                layout.addWidget(make_label(region))
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)


class SamplingRateList(QWidget):
    """A widget to display the list of sampling rates of the device."""

    def __init__(self, sampling_rates: List[SamplingRate]):
        super().__init__()

        def make_labels(sampling_rate: SamplingRate) -> Tuple[QLabel, QLabel, QLabel]:
            id_label = QLabel(f"[{sampling_rate.identifier}]  ")
            name = "<no name>"
            if len(sampling_rate.name) > 0:
                name = sampling_rate.name
            name_label = QLabel(f"{name}  ")
            freq_label = QLabel()

            if isinstance(sampling_rate, FixedFreqSamplingRate):
                freq_label.setText(f"({sampling_rate.frequency:0.1f}Hz)")
            elif isinstance(sampling_rate, VariableFreqSamplingRate):
                freq_label.setText("(Variable)")
            else:
                NotImplementedError("Unsupported sampling rate type")
            all_labels = (id_label, name_label, freq_label)
            for label in all_labels:
                _configure_value_label(label)
            return all_labels

        layout: Union[QVBoxLayout, QGridLayout]
        if len(sampling_rates) == 0:
            layout = QVBoxLayout(self)
            label = QLabel("None")
            _configure_value_label(label)
            layout.addWidget(label)
        else:
            layout = QGridLayout()

            layout.setHorizontalSpacing(0)
            layout.setVerticalSpacing(0)

            for i in range(len(sampling_rates)):
                labels = make_labels(sampling_rates[i])
                for j in range(len(labels)):
                    layout.addWidget(labels[j], i, j)
                    layout.setColumnStretch(j, 100 if j == len(labels) - 1 else 0)

        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)


class DeviceInfoDisplayTable(QWidget):
    """A table of properties/value. One per section displayed in DeviceInfoDialog"""
    form_layout: QFormLayout

    def __init__(self) -> None:
        super().__init__()
        self.form_layout = QFormLayout(self)
        self.form_layout.setFormAlignment(Qt.AlignmentFlag.AlignVCenter)

    def add_row(self, label_txt: str, item: Union[str, QWidget], tooltip: Optional[str] = None) -> None:
        label = QLabel(label_txt)
        has_tooltip = True if tooltip is not None else False
        _configure_property_label(label, has_tooltip=has_tooltip)
        if tooltip is not None:
            label.setToolTip(tooltip)
        if isinstance(item, str):
            item = QLabel(item)

        if isinstance(item, QLabel):
            _configure_value_label(item)

        is_odd = self.form_layout.rowCount() % 2 == 0    # Check for 0 because we evaluate for next node
        odd_even = "odd" if is_odd else "even"
        label.setProperty("table_odd_even", odd_even)
        item.setProperty("table_odd_even", odd_even)

        self.form_layout.addRow(label, item)


class DeviceInfoDialog(QDialog):
    """Window that display the device information, including capabilities and configuration"""

    def __init__(self, parent: Optional[QWidget], info: DeviceInfo) -> None:
        super().__init__(parent)

        self.setWindowTitle("Device")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setModal(True)

        def add_section(title: str) -> QVBoxLayout:
            gb = QGroupBox()
            gb.setTitle(title)
            layout.addWidget(gb)
            internal_layout = QVBoxLayout(gb)
            internal_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            return internal_layout

        def add_section_table(title: str) -> DeviceInfoDisplayTable:
            table = DeviceInfoDisplayTable()
            table_layout = add_section(title)
            table_layout.addWidget(table)
            return table

        def add_section_text(title: str, text: str) -> QLabel:
            text_layout = add_section(title)
            label = QLabel(text)
            _configure_value_label(label)
            text_layout.addWidget(label)
            return label

        device_table = add_section_table("Device")
        comm_table = add_section_table("Communication")

        device_table.add_row("Device ID", info.device_id,
                             tooltip="The firmware unique hash injected during build and used to identify the firmware")
        device_table.add_row("Display name", info.display_name,
                             tooltip="A textual name hardcoded in the firmware")
        device_table.add_row("Addresses size", f"{info.address_size_bits} bits",
                             tooltip="The size of a void* in the firmware")
        device_table.add_row("Supported features", SupportedFeatureList(info.supported_features),
                             tooltip="List of configurable feature enabled or disabled at build time")
        device_table.add_row("Read-only memory regions",
                             MemoryRegionList(info.readonly_memory_regions, info.address_size_bits),
                             tooltip="List of memory region that the device will refuse to write through Scrutiny")
        device_table.add_row("Forbidden memory regions",
                             MemoryRegionList(info.forbidden_memory_regions, info.address_size_bits),
                             tooltip="List of memory regions that the device will refuse to access through Scrutiny")

        comm_table.add_row("Protocol version", f"V{info.protocol_major}.{info.protocol_minor}",
                           tooltip="The version of protocol used between the server and the device")
        comm_table.add_row("Rx buffer size", f"{info.max_rx_data_size} bytes",
                           tooltip="Size of the communication buffer allocated for reception in the firmware")
        comm_table.add_row("Tx buffer size", f"{info.max_tx_data_size} bytes",
                           tooltip="Size of the communication buffer allocated for transmission in the firmware")
        bitrate_str = f"{info.max_bitrate_bps} bps" if info.max_bitrate_bps is not None else "N/A"
        comm_table.add_row("Max bitrate", bitrate_str,
                           tooltip="Optional maximum bitrate set by the device and enforced by the server.")
        comm_table.add_row("Heartbeat timeout", f"{info.heartbeat_timeout:0.1f} seconds",
                           tooltip="Amount of time required for the device to declare the server gone when no heartbeat messages are received")
        comm_table.add_row("Comm timeout", f"{info.rx_timeout_us} us",
                           tooltip="Maximum amount of time that the device will wait between the reception of 2 chunks of data to keep reassembling the transmitted datagram.")

        datalogging_title = "Datalogging"
        if info.datalogging_capabilities is None:   # Will happen if the feature is disabled in the device
            add_section_text(datalogging_title, "N/A")
        else:
            datalogging_table = add_section_table(datalogging_title)
            datalogging_table.add_row("Buffer size", f"{info.datalogging_capabilities.buffer_size} bytes",
                                      tooltip="Size of the buffer allocated to the datalogger. A bigger buffer means longer acquisition")
            datalogging_table.add_row("Encoding", f"{info.datalogging_capabilities.encoding.name}",
                                      tooltip="Data encoding scheme used by the device when making an acquisition.")
            datalogging_table.add_row("Max signals", f"{info.datalogging_capabilities.max_nb_signal}",
                                      tooltip="Maximum number of watchables to record during an acquisition")
            datalogging_table.add_row("Sampling rates", SamplingRateList(info.datalogging_capabilities.sampling_rates),
                                      tooltip="List of available sampling rates for the datalogger.")
