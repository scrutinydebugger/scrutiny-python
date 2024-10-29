#    device_info_dialog.py
#        A dialog to visualize the device information downlaoded after a device has connected.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['DeviceInfoDialog']

from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QWidget, QVBoxLayout, QGroupBox, QGridLayout
from PySide6.QtCore import Qt
from typing import Optional, List, Union, Tuple

from scrutiny.sdk import DeviceInfo, SupportedFeatureMap, MemoryRegion, SamplingRate, FixedFreqSamplingRate, VariableFreqSamplingRate

def configure_label(label:QLabel) -> None:
    label.setCursor(Qt.CursorShape.IBeamCursor)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

class SupportedFeatureList(QWidget):
    def __init__(self, features:SupportedFeatureMap):
        super().__init__()
        layout = QFormLayout(self)
        layout.setContentsMargins(0,0,0,0)
        feature_list = [
            ("Memory write", features.memory_write),
            ("Datalogging", features.datalogging),
            ("64 bits", features.sixtyfour_bits),
            ("User command", features.user_command)
        ]
        for feature in feature_list:
            title, enable = feature
            if enable:
                value_label = QLabel("Yes")
            else:
                value_label = QLabel("No")
            
            value_label.setProperty("feature_enable", enable)
            feature_label = QLabel(f"- {title} :")
            for label in [feature_label, value_label]:
                configure_label(label)
            layout.addRow(feature_label, label)
        
        layout.setSpacing(1)

class MemoryRegionList(QWidget):
    def __init__(self, regions:List[MemoryRegion], address_size_bits:int=64):
        super().__init__()
        address_size = address_size_bits//8
        if address_size%2 == 1:
            address_size += 1

        def make_label(region:MemoryRegion) -> QLabel:
            format_string = f"0x%0{address_size}X"
            s1 =  format_string % region.start
            s2 =  format_string % region.end
            label =  QLabel(f"- {s1}-{s2}")
            configure_label(label)
            return label

        layout:Union[QVBoxLayout, QFormLayout]
        if len(regions) == 0:
            layout = QVBoxLayout(self)
            label = QLabel("None")
            configure_label(label)
            layout.addWidget( label )
        else:
            layout = QFormLayout()
            for region in regions:
                layout.addWidget( make_label(region) )
        layout.setContentsMargins(0,0,0,0)
        self.setLayout(layout)

class SamplingRateList(QWidget):
    def __init__(self, sampling_rates:List[SamplingRate]):
        super().__init__()

        def make_labels(sampling_rate:SamplingRate) -> Tuple[QLabel, QLabel, QLabel]:
            id_label = QLabel(f"[{sampling_rate.identifier}]  ")
            name_label = QLabel(f"{sampling_rate.name}  ")
            freq_label = QLabel()

            if isinstance(sampling_rate, FixedFreqSamplingRate):
                freq_label.setText(f"({sampling_rate.frequency:0.1f}Hz)")
            elif isinstance(sampling_rate, VariableFreqSamplingRate):
                freq_label.setText("(Variable)")
            else:
                NotImplementedError("Unsupported sampling rate type")
            all_labels = (id_label, name_label, freq_label)
            for label in all_labels:
                configure_label(label)
            return all_labels

        layout:Union[QVBoxLayout, QGridLayout]
        if len(sampling_rates) == 0:
            layout = QVBoxLayout(self)
            label = QLabel("None")
            configure_label(label)
            layout.addWidget( label )
        else:
            layout = QGridLayout()
            
            layout.setHorizontalSpacing(0)
            layout.setVerticalSpacing(0)
            
            for i in range(len(sampling_rates)):
                labels = make_labels(sampling_rates[i])
                for j in range(len(labels)):
                    layout.addWidget(labels[j], i, j)
                    layout.setColumnStretch(j, 100 if j == len(labels)-1 else 0)


        layout.setContentsMargins(0,0,0,0)
        self.setLayout(layout)

class DeviceInfoDisplayTable(QWidget):
    form_layout : QFormLayout
    def __init__(self) -> None:
        super().__init__()
        self.form_layout = QFormLayout(self)
        self.form_layout.setFormAlignment(Qt.AlignmentFlag.AlignVCenter)
        
    
    def add_row(self, label_txt:str, item:Union[str, QWidget]) -> None:
        label = QLabel(label_txt)
        configure_label(label)
        if isinstance(item, str):
            item=QLabel(item)
        
        if isinstance(item, QLabel):
            configure_label(item)

        is_odd = self.form_layout.rowCount() % 2 == 0    # Check for 0 because we evaluate for next node
        odd_even = "odd" if is_odd else "even"
        label.setProperty("table_odd_even", odd_even)
        item.setProperty("table_odd_even", odd_even)

        self.form_layout.addRow(label, item)
        

class DeviceInfoDialog(QDialog):
    def __init__(self, parent:Optional[QWidget], info:DeviceInfo) -> None:
        super().__init__(parent) 

        self.setWindowTitle("Device")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        def add_section(title:str) -> QVBoxLayout:
            gb = QGroupBox()
            gb.setTitle(title)
            layout.addWidget(gb)
            internal_layout = QVBoxLayout(gb)
            internal_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            return internal_layout

        def add_section_table(title:str) -> DeviceInfoDisplayTable:
            table = DeviceInfoDisplayTable()
            table_layout = add_section(title)
            table_layout.addWidget(table)
            return table
        
        def add_section_text(title:str, text:str) -> QLabel:
            text_layout = add_section(title)
            label = QLabel(text)
            configure_label(label)
            text_layout.addWidget(label)
            return label

        device_table = add_section_table("Device")
        comm_table = add_section_table("Communication")

        device_table.add_row("Device ID", info.device_id)
        device_table.add_row("Display name", info.display_name)
        device_table.add_row("Addresses size", f"{info.address_size_bits} bits")
        device_table.add_row("Supported features", SupportedFeatureList(info.supported_features) )
        device_table.add_row("Read-only memory regions", MemoryRegionList(info.readonly_memory_regions, info.address_size_bits) )
        device_table.add_row("Forbidden memory regions",  MemoryRegionList(info.forbidden_memory_regions, info.address_size_bits) )

        comm_table.add_row("Protocol version", f"V{info.protocol_major}.{info.protocol_minor}")
        comm_table.add_row("Rx buffer size", f"{info.max_rx_data_size} bytes")
        comm_table.add_row("Tx buffer size", f"{info.max_tx_data_size} bytes")
        bitrate_str = f"{info.max_bitrate_bps} bps" if info.max_bitrate_bps is not None else "N/A"
        comm_table.add_row("Max bitrate", bitrate_str)
        comm_table.add_row("Heartbeat timeout", f"{info.heartbeat_timeout:0.1f} seconds")
        comm_table.add_row("Comm timeout", f"{info.rx_timeout_us} us")

        datalogging_title="Datalogging"
        if info.datalogging_capabilities is None:   # Will happen if the feature is disabled in the device
            add_section_text(datalogging_title, "N/A")
        else:
            datalogging_table = add_section_table(datalogging_title)
            datalogging_table.add_row("Buffer size", f"{info.datalogging_capabilities.buffer_size} bytes")
            datalogging_table.add_row("Encoding", f"{info.datalogging_capabilities.encoding.name}")
            datalogging_table.add_row("Max signals", f"{info.datalogging_capabilities.max_nb_signal}")
            datalogging_table.add_row("Sampling rates", SamplingRateList(info.datalogging_capabilities.sampling_rates))
