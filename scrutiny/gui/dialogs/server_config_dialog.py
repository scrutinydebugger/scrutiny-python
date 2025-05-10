#    server_config_dialog.py
#        A dialog to edit the connection parameter of the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['ServerConfigDialog']

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QWidget, QVBoxLayout,QPushButton, QHBoxLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator

from scrutiny.gui.tools.validators import IpPortValidator, NotEmptyValidator
from scrutiny.gui.widgets.validable_line_edit import ValidableLineEdit
from scrutiny.gui.widgets.feedback_label import FeedbackLabel
from scrutiny.gui.core.server_manager import ServerConfig
from scrutiny.gui.core.local_server_runner import LocalServerRunner
from scrutiny.gui.core.persistent_data import gui_persistent_data, AppPersistentData

from scrutiny import tools
from scrutiny.tools.typing import *

class LoadFromLocalServerWidget(QWidget):
    
    _feedback_label : FeedbackLabel
    _btn_connect:QPushButton

    @tools.copy_type(QWidget.__init__)
    def __init__(self, *args:Any, **kwargs:Any) -> None:
        super().__init__(*args, **kwargs)

        self._feedback_label = FeedbackLabel(self)
        
        self._btn_connect = QPushButton("Connect to local server")
        layout = QHBoxLayout(self)
        layout.addWidget(self._feedback_label)
        layout.addWidget(self._btn_connect)
        layout.setContentsMargins(0,0,0,0)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
    def show_with_port(self, port:int) -> None:
        self._feedback_label.set_info(f"There is a local server running on port {port}")
        self.setVisible(True)

    def connect_btn(self) -> QPushButton:
        return self._btn_connect

    

class ServerConfigDialog(QDialog):
    class PersistentPreferences:
        HOSTNAME = 'server_hostname'
        PORT = 'server_port'

    DEFAULT_HOSTNAME = "localhost"
    DEFAULT_PORT = 8765

    _hostname:str
    _port:int
    _local_server_runner:LocalServerRunner
    _connect_to_local_server_wdiget:LoadFromLocalServerWidget

    _hostname_textbox:ValidableLineEdit
    _port_textbox:ValidableLineEdit
    _preferences:AppPersistentData

    _apply_callback:Callable[["ServerConfigDialog"], None]

    def __init__(self, 
                 parent:QWidget, 
                 apply_callback:Callable[["ServerConfigDialog"], None],
                 local_server_runner:LocalServerRunner) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.WindowTitleHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setWindowTitle("Server configuration")
        self._apply_callback = apply_callback
        self._preferences = gui_persistent_data.get_namespace(self.__class__.__name__)
        self._local_server_runner = local_server_runner
        self._connect_to_local_server_wdiget = LoadFromLocalServerWidget(self)
        self._connect_to_local_server_wdiget.setVisible(True)
    

        layout = QVBoxLayout(self)
        form = QWidget()
        # cast is for mypy issue
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(form)
        layout.addWidget(self._connect_to_local_server_wdiget)
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
        self._local_server_runner.signals.state_changed.connect(self._local_server_runner_update_state_slot)
        self._connect_to_local_server_wdiget.connect_btn().clicked.connect(self._connect_to_local_server)

        self.set_hostname(self._preferences.get_str(self.PersistentPreferences.HOSTNAME, self.DEFAULT_HOSTNAME))
        self.set_port(self._preferences.get_int(self.PersistentPreferences.PORT, self.DEFAULT_PORT))

        self._local_server_runner_update_state_slot(self._local_server_runner.get_state())
        

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

    def _local_server_runner_update_state_slot(self, state:LocalServerRunner.State) -> None:
        port = self._local_server_runner.get_port()
        if state == LocalServerRunner.State.STARTED and  port is not None:
            self._connect_to_local_server_wdiget.show_with_port(port)
        else:
            self._connect_to_local_server_wdiget.hide()
    
    def _connect_to_local_server(self) -> None:
        port = self._local_server_runner.get_port()
        if port is not None:
            self._port_textbox.setText(str(port))
            self._hostname_textbox.setText('localhost')
            self._apply_and_connect()


    def _btn_ok_click(self) -> None:
        self._apply_and_connect()

    def _apply_and_connect(self) -> None:
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
