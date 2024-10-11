#    server_config_dialog.py
#        A dialog to edit the connection parameter of the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['ServerConfigDialog']

from qtpy.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QWidget, QVBoxLayout
from qtpy.QtCore import Qt
from qtpy.QtGui import QPalette, QIntValidator


from typing import Callable


class ServerConfigDialog(QDialog):
    DEFAULT_HOSTNAME = "localhost"
    DEFAULT_PORT = 8765

    _hostname:str
    _port:int

    _hostname_textbox:QLineEdit
    _port_textbox:QLineEdit

    _apply_callback:Callable[[], None]

    def __init__(self, parent:QWidget, apply_callback:Callable[[], None]) -> None:
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
        self._hostname_textbox = QLineEdit()
        self._port_textbox = QLineEdit()

        self._port_textbox.setValidator(QIntValidator(1, 0xFFFF))
        
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
    
    
    def _validate(self) -> bool:
        port_valid = True
        try:
            port = int(self._port_textbox.text())
        except Exception:
            port_valid=False
        
        if port_valid:
            if port<=0 or port>0xFFFF:
                port_valid = False
        
        

    def _btn_ok_click(self) -> None:
        print(self._port_textbox.validator())
        self.close()
        self._apply_callback()

    def _btn_cancel_click(self) -> None:
        self.reset()
        self.close()
