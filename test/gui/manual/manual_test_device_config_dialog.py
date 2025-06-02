#    manual_test_device_config_dialog.py
#        Create an environment to manually test the DeviceConfigDialog window
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

if __name__ != '__main__' : 
    raise RuntimeError("This script is expected to run from the command line")

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from manual_test_base import make_manual_test_app
app = make_manual_test_app()

import logging
from PySide6.QtWidgets import QMainWindow, QPushButton, QWidget, QVBoxLayout
from scrutiny.gui.dialogs.device_config_dialog import DeviceConfigDialog
from scrutiny import sdk

def config_applied(dialog:DeviceConfigDialog):
    link_type, config = dialog.get_type_and_config()
    logging.info(f"Config applied: Link: {link_type}. Config : {config}")


window = QMainWindow()
central_widget = QWidget()
btn_show = QPushButton("show")
btn_fail = QPushButton("Simulate fail")
btn_success = QPushButton("Simulate success")
btn_show.setFixedSize(50,20)
window.setCentralWidget(central_widget)
layout = QVBoxLayout(central_widget)
layout.addWidget(btn_show)
layout.addWidget(btn_fail)
layout.addWidget(btn_success)
dialog = DeviceConfigDialog(apply_callback=config_applied )
dialog.set_config(sdk.DeviceLinkType.UDP, sdk.UDPLinkConfig(host="google.com", port=80))
dialog.set_config(sdk.DeviceLinkType.TCP, sdk.TCPLinkConfig(host="localhost", port=1234))

btn_show.clicked.connect(lambda: dialog.show())
btn_fail.clicked.connect(lambda: dialog.change_fail_callback("Failed"))
btn_success.clicked.connect(lambda: dialog.change_success_callback())
window.show()

sys.exit(app.exec())
