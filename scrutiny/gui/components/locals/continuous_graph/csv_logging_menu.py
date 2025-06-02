#    csv_logging_menu.py
#        A widget used to configure the continuous CSV logger
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['CsvLoggingMenuWidget']

from pathlib import Path
import logging
import re
import os

from PySide6.QtWidgets import (QHBoxLayout, QWidget, QVBoxLayout, QSizePolicy,
                               QPushButton, QFormLayout, QSpinBox,
                               QLineEdit, QCheckBox, QGroupBox, QMessageBox)
from PySide6.QtCore import Qt

from scrutiny.gui.tools import prompt
from scrutiny.gui.core.persistent_data import gui_persistent_data
from scrutiny.sdk.listeners.csv_logger import CSVLogger, CSVConfig
from scrutiny.tools.typing import *
from scrutiny.sdk.listeners.csv_logger import CSVLogger, CSVConfig


class CsvLoggingMenuWidget(QWidget):
    class SerializableState(TypedDict):
        enable: bool
        folder: str
        prefix: str
        line_per_files: int

    _chk_enable: QCheckBox
    _txt_folder: QLineEdit
    _txt_filename_pattern: QLineEdit
    _spin_max_line_per_file: QSpinBox
    _gb_content: QGroupBox

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._chk_enable = QCheckBox("Log to CSV", self)
        self._gb_content = QGroupBox(self)
        self._gb_content.setVisible(False)
        layout.addWidget(self._chk_enable)
        layout.addWidget(self._gb_content)
        self._txt_folder = QLineEdit(self)
        self._txt_filename_pattern = QLineEdit(self)
        self._spin_max_line_per_file = QSpinBox(self)
        self._spin_max_line_per_file.setMinimum(1000)
        self._spin_max_line_per_file.setMaximum(1000000)
        self._spin_max_line_per_file.setValue(10000)
        self._btn_browse = QPushButton("...", self)
        self._txt_folder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._btn_browse.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        self._btn_browse.setMinimumWidth(20)
        self._btn_browse.setMaximumWidth(40)

        self._btn_browse.clicked.connect(self._browse_clicked_slot)

        filebrowse_line = QWidget()
        filebrowse_layout = QHBoxLayout(filebrowse_line)
        filebrowse_layout.setContentsMargins(0, 0, 0, 0)
        filebrowse_layout.addWidget(self._txt_folder)
        filebrowse_layout.addWidget(self._btn_browse)

        gb_layout = QFormLayout(self._gb_content)

        gb_layout.addRow("Folder", filebrowse_line)
        gb_layout.addRow("File prefix", self._txt_filename_pattern)
        gb_layout.addRow("Lines/file", self._spin_max_line_per_file)

        self._chk_enable.checkStateChanged.connect(self._check_state_changed_slot)

        self.setTabOrder(self._chk_enable, self._txt_folder)
        self.setTabOrder(self._txt_folder, self._btn_browse)
        self.setTabOrder(self._btn_browse, self._txt_filename_pattern)
        self.setTabOrder(self._txt_filename_pattern, self._spin_max_line_per_file)

    def _check_state_changed_slot(self, state: Qt.CheckState) -> None:
        if state == Qt.CheckState.Checked:
            self._gb_content.setVisible(True)
        else:
            self._gb_content.setVisible(False)

    def _browse_clicked_slot(self) -> None:
        actual_folder: Optional[Path] = None  # USe last save dir if None
        if os.path.isdir(self._txt_folder.text()):
            actual_folder = Path(os.path.normpath(self._txt_folder.text()))
            actual_folder = actual_folder.absolute()

        folder = prompt.get_save_folderpath_from_last_save_dir(self, "Select a folder", save_dir=actual_folder)
        if folder is not None:
            self._txt_folder.setText(str(folder))

    def require_csv_logging(self) -> bool:
        return self._chk_enable.isChecked()

    def validate(self) -> None:
        folder = self._txt_folder.text()
        if len(folder) == 0:
            raise ValueError("No folder selected")
        filename_pattern = self._txt_filename_pattern.text()
        if len(filename_pattern) == 0:
            raise ValueError("No filename prefix provided")

        valid_filename = re.compile(r"^[A-Za-z0-9\._\-\(\)]+$")
        if not valid_filename.match(filename_pattern):
            raise ValueError("Invalid characters in filename")

        folder = os.path.normpath(folder)
        if not os.path.isabs(folder):
            folder = os.path.normpath(os.path.abspath(folder))

        if not os.path.isdir(folder):
            raise FileNotFoundError(f"Folder {folder} does not exist")

        self._txt_folder.setText(folder)

    def check_conflicts(self) -> bool:
        self.validate()

        folder = Path(self._txt_folder.text())
        filename = self._txt_filename_pattern.text()

        conflicting_files = list(CSVLogger.get_conflicting_files(folder, filename))
        if len(conflicting_files) == 0:
            return True

        MAX_NAME_DISPLAY = 3
        msgbox_text = f"There are {len(conflicting_files)} existing files that may conflict with the given folder/name combination.\n"
        msgbox_text += '\n'.join([f"  - {file.name}" for file in conflicting_files[:MAX_NAME_DISPLAY]]) + '\n'
        if len(conflicting_files) > MAX_NAME_DISPLAY:
            diff = len(conflicting_files) - MAX_NAME_DISPLAY
            msgbox_text += f'  - And {diff} others\n'

        msgbox_text += '\n Do you want to delete them?'

        override = prompt.warning_yes_no_question(self, msg=msgbox_text, title="Filename conflict")

        if override:
            for file in conflicting_files:
                os.unlink(file)
            return True
        else:
            return False

    def get_state(self) -> SerializableState:
        return {
            'enable': self._chk_enable.isChecked(),
            'folder': self._txt_folder.text(),
            'line_per_files': self._spin_max_line_per_file.value(),
            'prefix': self._txt_filename_pattern.text()
        }

    def load_state(self, state: SerializableState) -> bool:
        fully_valid = True
        if 'enable' in state and isinstance(state['enable'], bool):
            self._chk_enable.setChecked(state['enable'])
        else:
            fully_valid = False

        if 'folder' in state and isinstance(state['folder'], str):
            if os.path.isdir(state['folder']):
                self._txt_folder.setText(state['folder'])
            else:
                self._txt_folder.setText("")
        else:
            fully_valid = False

        if 'line_per_files' in state and isinstance(state['line_per_files'], int):
            self._spin_max_line_per_file.setValue(state['line_per_files'])
        else:
            fully_valid = fully_valid

        if 'prefix' in state and isinstance(state['prefix'], str):
            self._txt_filename_pattern.setText(state['prefix'])
        else:
            fully_valid = fully_valid

        return fully_valid

    def make_csv_logger(self, logging_logger: Optional[logging.Logger] = None) -> CSVLogger:
        # Validation happens inside the constructor
        self.validate()

        csv_config = CSVConfig(
            delimiter=',',
            newline='\n'
        )

        return CSVLogger(
            folder=self._txt_folder.text(),
            filename=self._txt_filename_pattern.text(),
            lines_per_file=self._spin_max_line_per_file.value(),
            datetime_format=gui_persistent_data.global_namespace().long_datetime_format(),
            csv_config=csv_config,
            convert_bool_to_int=True,
            logger=logging_logger,
            file_part_0pad=4
        )
