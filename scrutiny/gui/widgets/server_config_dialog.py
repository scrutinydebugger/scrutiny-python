#    server_config_dialog.py
#        A dialog to edit the connection parameter of the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['ServerConfigDialog']

from qtpy.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QWidget, QVBoxLayout
from qtpy.QtCore import Qt
from qtpy.QtGui import QIntValidator
from scrutiny.gui.tools.validators import IpPortValidator, NotEmptyValidator
from scrutiny.gui.widgets.validable_line_edit import ValidableLineEdit
from scrutiny.gui.core.server_manager import ServerConfig

from typing import Callable, Optional


class ServerConfigDialog(QDialog):
    DEFAULT_HOSTNAME = "localhost"
    DEFAULT_PORT = 8765

    _hostname:str
    _port:int

    _hostname_textbox:ValidableLineEdit
    _port_textbox:ValidableLineEdit

    _apply_callback:Optional[Callable[[], None]]

    def __init__(self, parent:QWidget, apply_callback:Optional[Callable[[], None]]=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.WindowTitleHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setWindowTitle("Server configuration")
        self._apply_callback = apply_callback

        layout = QVBoxLayout(self)
        form = QWidget()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(form)
        layout.addWidget(buttons)

        form_layout = QFormLayout(form)
        form_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        hostname_label = QLabel("Hostname: ")
        port_label = QLabel("Port: ")
        self._hostname_textbox = ValidableLineEdit(soft_validator=NotEmptyValidator())
        self._port_textbox = ValidableLineEdit(hard_validator=QIntValidator(0,0xFFFF), soft_validator=IpPortValidator())

        self._hostname_textbox.textChanged.connect(self._hostname_textbox.validate_expect_not_wrong)
        self._port_textbox.textChanged.connect(self._port_textbox.validate_expect_not_wrong)
        
        form_layout.addRow(hostname_label, self._hostname_textbox)
        form_layout.addRow(port_label, self._port_textbox)

        buttons.accepted.connect(self._btn_ok_click)
        buttons.rejected.connect(self._btn_cancel_click)

        self.set_port(self.DEFAULT_PORT)
        self.set_hostname(self.DEFAULT_HOSTNAME)

    def get_port(self) -> int:
        return self._port

    def get_hostname(self) -> str:
        return self._hostname
    
    def set_port(self, port:int) -> None:
        self._port = port
        self._port_textbox.setText(str(port))

    def set_hostname(self, hostname:str) -> None:
        self._hostname = hostname
        self._hostname_textbox.setText(hostname)

    def reset(self) -> None:
        self.set_hostname(self.get_hostname())
        self.set_port(self.get_port())
        self._port_textbox.default_style()
        self._hostname_textbox.default_style()
    
    def _validate(self) -> bool:
        port_valid = self._port_textbox.validate_expect_valid()
        host_valid = self._hostname_textbox.validate_expect_valid()
        return port_valid and host_valid

    
    def _btn_ok_click(self) -> None:
        valid_config = self._validate()
        if valid_config:
            self._hostname = self._hostname_textbox.text()
            self._port = int(self._port_textbox.text()) # Validator is supposed to guarantee the validity of this
            self.close()
            if self._apply_callback is not None:
                self._apply_callback()

    def _btn_cancel_click(self) -> None:
        self.reset()
        self._validate()
        self.close()

    def get_config(self) -> ServerConfig:
        return ServerConfig(
            hostname=self.get_hostname(),
            port=self.get_port()
        )
