
if __name__ != '__main__' : 
    raise RuntimeError("This script is expected to run from the command line")

import sys, os
os.environ['SCRUTINY_MANUAL_TEST'] = '1'
project_root = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)

import logging
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFormLayout
from scrutiny.gui import assets

from scrutiny.gui.dashboard_components.varlist.varlist_component import VarListComponent
from scrutiny.gui.dashboard_components.watch.watch_component import WatchComponent
from scrutiny.gui.core.watchable_registry import WatchableRegistry

from test.gui.fake_server_manager import FakeServerManager, ServerConfig

logging.basicConfig(level=logging.DEBUG)

app = QApplication([])
app.setStyleSheet(assets.load_text(["stylesheets", "scrutiny_base.qss"]))

window = QMainWindow()
central_widget = QWidget()
window.setCentralWidget(central_widget)

registry = WatchableRegistry()
server_manager = FakeServerManager(registry)

vlayout = QVBoxLayout(central_widget)

btn_start = QPushButton("Start")
btn_stop = QPushButton("Stop")
btn_connect = QPushButton("Connect server")
btn_disconnect = QPushButton("Disconnect server")
btn_device_ready = QPushButton("Connect Device")
btn_device_gone = QPushButton("Diconnect Device")
btn_load_sfd = QPushButton("Load Sfd")
btn_unload_sfd = QPushButton("Unload SFD")

button_container = QWidget()
component_container = QWidget()
status_container = QWidget()
vlayout.addWidget(button_container)
vlayout.addWidget(component_container)
vlayout.addWidget(status_container)

button_layout = QHBoxLayout(button_container)
button_layout.addWidget(btn_start)
button_layout.addWidget(btn_stop)
button_layout.addWidget(btn_connect)
button_layout.addWidget(btn_disconnect)
button_layout.addWidget(btn_device_ready)
button_layout.addWidget(btn_device_gone)
button_layout.addWidget(btn_load_sfd)
button_layout.addWidget(btn_unload_sfd)

component_layout = QHBoxLayout(component_container)

varlist = VarListComponent(main_window=window, instance_name="varlist1", server_manager=server_manager)
watch1 = WatchComponent(main_window=window, instance_name="watch1", server_manager=server_manager)
watch2 = WatchComponent(main_window=window, instance_name="watch2", server_manager=server_manager)

varlist.setup()
watch1.setup()
watch2.setup()

component_layout.addWidget(varlist)
component_layout.addWidget(watch1)
component_layout.addWidget(watch2)

status_layout = QFormLayout(status_container)
running_label = QLabel("")
server_connected_label = QLabel("")
device_connected_label = QLabel("")
sfd_loaded_label = QLabel("")

status_layout.addRow("Manager state: ", running_label)
status_layout.addRow("Server: ", server_connected_label)
status_layout.addRow("Device: ", device_connected_label)
status_layout.addRow("SFD: ", sfd_loaded_label)

window.show()

def update_ui():
    btn_start.setEnabled(not server_manager.is_running())
    btn_stop.setEnabled(server_manager.is_running())
    server_connected = server_manager.get_server_info() is not None
    if server_manager.is_running():
        btn_connect.setEnabled(not server_connected)
        btn_disconnect.setEnabled(server_connected)
        if server_connected:
            btn_device_ready.setEnabled(not server_manager._device_connected)
            btn_device_gone.setEnabled(server_manager._device_connected)
            btn_load_sfd.setEnabled(not server_manager._sfd_loaded)
            btn_unload_sfd.setEnabled(server_manager._sfd_loaded)
        else:
            btn_device_ready.setEnabled(False)
            btn_device_gone.setEnabled(False)
            btn_load_sfd.setEnabled(False)
            btn_unload_sfd.setEnabled(False)
    else:
        btn_connect.setEnabled(False)
        btn_disconnect.setEnabled(False)
        btn_device_ready.setEnabled(False)
        btn_device_gone.setEnabled(False)
        btn_load_sfd.setEnabled(False)
        btn_unload_sfd.setEnabled(False)

    running_label.setText("Running" if server_manager.is_running() else "Stopped")
    server_connected_label.setText("Connected" if server_connected else "Disconnected")
    device_connected_label.setText( "Connected" if server_manager._device_connected else "Disconnected")
    sfd_loaded_label.setText( "Loaded" if server_manager._sfd_loaded else "Unloaded")


def btn_start_slot():
    server_manager.start(ServerConfig(hostname='localhost', port=12345))
    update_ui()

def btn_stop_slot():
    server_manager.stop()
    update_ui()

def btn_connect_slot():
    server_manager.simulate_server_connect()
    update_ui()

def btn_disconnect_slot():
    server_manager.simulate_server_disconnected()
    update_ui()

def btn_device_ready_slot():
    server_manager.simulate_device_ready()
    update_ui()

def btn_device_gone_slot():
    server_manager.simulate_device_disconnect()
    update_ui()

def btn_load_sfd_slot():
    server_manager.simulate_sfd_loaded()
    update_ui()

def btn_unload_sfd_slot():
    server_manager.simulate_sfd_unloaded()
    update_ui()

btn_start.clicked.connect(btn_start_slot)
btn_stop.clicked.connect(btn_stop_slot)
btn_connect.clicked.connect(btn_connect_slot)
btn_disconnect.clicked.connect(btn_disconnect_slot)
btn_device_ready.clicked.connect(btn_device_ready_slot)
btn_device_gone.clicked.connect(btn_device_gone_slot)
btn_load_sfd.clicked.connect(btn_load_sfd_slot)
btn_unload_sfd.clicked.connect(btn_unload_sfd_slot)

update_ui()


sys.exit(app.exec())
