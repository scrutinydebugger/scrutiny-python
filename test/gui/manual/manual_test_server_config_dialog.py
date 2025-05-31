#    manual_test_server_config_dialog.py
#        A manual test suite for checking the behaviour of the server config dialog
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2021 Scrutiny Debugger

if __name__ != '__main__' : 
    raise RuntimeError("This script is expected to run from the command line")

import sys, os


sys.path.insert(0, os.path.dirname(__file__))
from manual_test_base import make_manual_test_app
app = make_manual_test_app()

import scrutiny.entry_point
from scrutiny.gui.dialogs.server_config_dialog import ServerConfigDialog
from scrutiny.gui.core.local_server_runner import LocalServerRunner

from PySide6.QtWidgets import QMainWindow, QPushButton, QWidget, QVBoxLayout, QCheckBox
from PySide6.QtCore import Qt



window = QMainWindow()
central_widget = QWidget()
btn_show = QPushButton("show")
chk_force_no_executable = QCheckBox("Simulate no binary")

window.setCentralWidget(central_widget)
layout = QVBoxLayout(central_widget)
layout.addWidget(btn_show)
layout.addWidget(chk_force_no_executable)
def callback(dialog:ServerConfigDialog) -> None:
    print("callback. Config = %s" % dialog.get_config())
runner = LocalServerRunner()
dialog = ServerConfigDialog(parent=None, apply_callback=callback, local_server_runner=runner)

def chk_force_no_executable_state_changed_slot(state:Qt.CheckState):
    if state == Qt.CheckState.Checked:
        runner.emulate_no_cli(True)
    else:
        runner.emulate_no_cli(False)


btn_show.clicked.connect(lambda: dialog.show())
chk_force_no_executable.checkStateChanged.connect(chk_force_no_executable_state_changed_slot)

app.aboutToQuit.connect(runner.stop)

window.show()
sys.exit(app.exec())
