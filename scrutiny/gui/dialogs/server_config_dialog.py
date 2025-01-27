#    server_config_dialog.py
#        A dialog to edit the connection parameter of the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['ServerConfigDialog']

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QWidget, QVBoxLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator
from scrutiny.gui.tools.validators import IpPortValidator, NotEmptyValidator
from scrutiny.gui.widgets.validable_line_edit import ValidableLineEdit
from scrutiny.gui.core.server_manager import ServerConfig
from scrutiny.gui.core.preferences import gui_preferences, AppPreferences

from typing import Callable


class ServerConfigDialog(QDialog):
    class PersistentPreferences:
        HOSTNAME = 'server_hostname'
        PORT = 'server_port'

    DEFAULT_HOSTNAME = "localhost"
    DEFAULT_PORT = 8765

    _hostname:str
    _port:int

    _hostname_textbox:ValidableLineEdit
    _port_textbox:ValidableLineEdit
    _preferences:AppPreferences

    _apply_callback:Callable[["ServerConfigDialog"], None]

    def __init__(self, parent:QWidget, apply_callback:Callable[["ServerConfigDialog"], None]) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.WindowTitleHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setWindowTitle("Server configuration")
        self._apply_callback = apply_callback
        self._preferences = gui_preferences.get_namespace(self.__class__.__name__)

        layout = QVBoxLayout(self)
        form = QWidget()
        # cast is for mypy issue
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(form)
        layout.addWidget(buttons)

        form_layout = QFormLayout(form)
        form_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        hostname_label = QLabel("Hostname: ")
        port_label = QLabel("Port: ")
        self._hostname_textbox = ValidableLineEdit(soft_validator=NotEmptyValidator())
        self._port_textbox = ValidableLineEdit(hard_validator=QIntValidator(0,0xFFFF), soft_validator=IpPortValidator())

        self._hostname_textbox.textChanged.connect(self._hostname_textbox.validate_expect_not_wrong_default_slot)
        self._port_textbox.textChanged.connect(self._port_textbox.validate_expect_not_wrong_default_slot)
        
        form_layout.addRow(hostname_label, self._hostname_textbox)
        form_layout.addRow(port_label, self._port_textbox)

        buttons.accepted.connect(self._btn_ok_click)
        buttons.rejected.connect(self._btn_cancel_click)

        self.set_hostname(self._preferences.get_str(self.PersistentPreferences.HOSTNAME, self.DEFAULT_HOSTNAME))
        self.set_port(self._preferences.get_int(self.PersistentPreferences.PORT, self.DEFAULT_PORT))

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
            self._preferences.set(self.PersistentPreferences.HOSTNAME, self._hostname)
            self._preferences.set(self.PersistentPreferences.PORT, self._port)
            self._apply_callback(self)
            self.close()

    def _btn_cancel_click(self) -> None:
        self.reset()
        self._validate()
        self.close()

    def get_config(self) -> ServerConfig:
        return ServerConfig(
            hostname=self.get_hostname(),
            port=self.get_port()
        )
