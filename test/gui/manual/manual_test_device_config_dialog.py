
if __name__ != '__main__' : 
    raise RuntimeError("This script is expected to run from the command line")

import sys, os
project_root = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)

import logging
from qtpy.QtWidgets import QApplication, QMainWindow, QPushButton
from scrutiny.gui.dialogs.device_config_dialog import DeviceConfigDialog
from scrutiny import sdk
from scrutiny.gui import assets
import functools

logging.basicConfig(level=logging.DEBUG)


def config_applied(dialog:DeviceConfigDialog):
    link_type, config = dialog.get_type_and_config()
    logging.info(f"Config applied: Link: {link_type}. Config : {config}")


app = QApplication([])
app.setStyleSheet(assets.load_text(["stylesheets", "scrutiny_base.qss"]))

window = QMainWindow()
btn = QPushButton("show")
btn.setFixedSize(50,20)
window.setCentralWidget(btn)
dialog = DeviceConfigDialog(apply_callback=config_applied )
dialog.set_config(sdk.DeviceLinkType.UDP, sdk.UDPLinkConfig(host="google.com", port=80))
dialog.set_config(sdk.DeviceLinkType.TCP, sdk.TCPLinkConfig(host="localhost", port=1234))

btn.clicked.connect(lambda: dialog.show())

window.show()

sys.exit(app.exec())
