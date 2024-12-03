#    manual_test_sfd_content_dialog.py
#        Create an environment to manually test the SFDContentDialog window
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

if __name__ != '__main__' : 
    raise RuntimeError("This script is expected to run from the command line")

import sys, os
project_root = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)

import logging
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QWidget, QVBoxLayout
from scrutiny.gui.dialogs.sfd_content_dialog import SFDContentDialog
from scrutiny.gui import assets
from scrutiny.sdk import *
from dataclasses import dataclass
import scrutiny
import datetime

from typing import Optional, List
logging.basicConfig(level=logging.DEBUG)

@dataclass
class Config:
    add_ro_mem:bool = False
    add_forbidden_mem:bool = False
    add_datalogging:bool = False
    add_sampling_rates:bool = False

def make_sfd_info() -> SFDInfo:
    return SFDInfo(
        firmware_id="The firmware ID",
        metadata=SFDMetadata(
            author="Pier-Yves Lessard",
            project_name="Unit test project",
            version="V1.0.2",
            generation_info=SFDGenerationInfo(
                python_version="The python version",
                scrutiny_version=f"{scrutiny.__version__}",
                system_type="Win32",
                timestamp=datetime.datetime.now()
            )
        )
    )

app = QApplication([])
app.setStyleSheet(assets.load_text(["stylesheets", "scrutiny_base.qss"]))

window = QMainWindow()
central_widget = QWidget()
btn_show = QPushButton("Show")
dialog = SFDContentDialog(window, make_sfd_info())
window.setCentralWidget(central_widget)
layout = QVBoxLayout(central_widget)
layout.addWidget(btn_show)

btn_show.clicked.connect(lambda: dialog.show())
window.show()

sys.exit(app.exec())