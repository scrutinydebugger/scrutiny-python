#    sfd_content_dialog.py
#        Window that displays the metadata associated with a Scrutiny Firmware Description
#        file
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

__all__ = ['SFDContentDialog']

from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QWidget, QVBoxLayout, QGroupBox
from PySide6.QtCore import Qt
from scrutiny import sdk
from scrutiny.tools.typing import *


class SFDContentDialog(QDialog):
    def __init__(self, parent: Optional[QWidget], sfd: sdk.SFDInfo) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setWindowTitle("Scrutiny Firmware Description (SFD)")
        self.setMinimumWidth(300)
        basic_gb = QGroupBox()
        project_gb = QGroupBox()
        sfd_generation_gb = QGroupBox()
        layout.addWidget(basic_gb)
        layout.addWidget(project_gb)
        layout.addWidget(sfd_generation_gb)
        basic_gb.setTitle("Basic")
        project_gb.setTitle("Project")
        sfd_generation_gb.setTitle("SFD Generation")
        self.setModal(True)

        def write_fields(gb: QGroupBox, fields: List[Tuple[str, Optional[str]]]) -> None:
            layout = QFormLayout(gb)
            for field in fields:
                property_label = QLabel(f"{field[0]}: ")
                value = "N/A"
                if field[1] is not None:
                    value = field[1]
                value_label = QLabel(value)
                property_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                property_label.setCursor(Qt.CursorShape.WhatsThisCursor)
                value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                value_label.setCursor(Qt.CursorShape.IBeamCursor)
                layout.addRow(property_label, value_label)

        def write_na(gb: QGroupBox) -> None:
            layout = QVBoxLayout(gb)
            label = QLabel("N/A")
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(label)

        write_fields(basic_gb, [("Firmware ID", sfd.firmware_id)])

        if sfd.metadata is None:
            write_na(project_gb)
        else:
            project_fields: List[Tuple[str, Optional[str]]] = [
                ("Project name", sfd.metadata.project_name),
                ("Version", sfd.metadata.version),
                ("Author", sfd.metadata.author)
            ]

            write_fields(project_gb, project_fields)

        if sfd.metadata is None or sfd.metadata.generation_info is None:
            write_na(sfd_generation_gb)
        else:
            dt: Optional[str] = None
            if sfd.metadata.generation_info.timestamp is not None:
                dt = sfd.metadata.generation_info.timestamp.strftime(r"%Y-%m-%d %H:%M:%S")
            sfd_generation_fields = [
                ("Scrutiny Version", sfd.metadata.generation_info.scrutiny_version),
                ("Python Version", sfd.metadata.generation_info.python_version),
                ("System", sfd.metadata.generation_info.system_type),
                ("Created on", dt)
            ]
            write_fields(sfd_generation_gb, sfd_generation_fields)
