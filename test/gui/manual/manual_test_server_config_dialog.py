
if __name__ != '__main__' : 
    raise RuntimeError("This script is expected to run from the command line")

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from manual_test_base import make_manual_test_app
app = make_manual_test_app()

from scrutiny.gui.dialogs.server_config_dialog import ServerConfigDialog
from scrutiny.gui.core.local_server_runner import LocalServerRunner

from PySide6.QtWidgets import QMainWindow, QPushButton, QWidget, QVBoxLayout

window = QMainWindow()
central_widget = QWidget()
btn_show = QPushButton("show")
window.setCentralWidget(central_widget)
layout = QVBoxLayout(central_widget)
layout.addWidget(btn_show)
def callback(dialog:ServerConfigDialog) -> None:
    print("callback. Config = %s" % dialog.get_config())
runner = LocalServerRunner()
dialog = ServerConfigDialog(parent=None, apply_callback=callback, local_server_runner=runner)

btn_show.clicked.connect(lambda: dialog.show())

app.aboutToQuit.connect(runner.stop)

window.show()
sys.exit(app.exec())
