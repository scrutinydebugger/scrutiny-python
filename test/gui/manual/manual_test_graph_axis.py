#    manual_test_graph_axis.py
#        A dummy app to test the graph axis tree widget
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

if __name__ != '__main__' : 
    raise RuntimeError("This script is expected to run from the command line")

import sys, os
os.environ['SCRUTINY_MANUAL_TEST'] = '1'
project_root = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)

import logging
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget,  QHBoxLayout
from scrutiny.gui import assets

from scrutiny.gui.dashboard_components.varlist.varlist_component import VarListComponent
from scrutiny.gui.dashboard_components.watch.watch_component import WatchComponent
from scrutiny.gui.core.watchable_registry import WatchableRegistry
from scrutiny.gui.dashboard_components.common.graph_signal_tree import GraphSignalModel, GraphSignalTree
from scrutiny.gui.core.threads import QT_THREAD_NAME
from scrutiny.tools.thread_enforcer import register_thread

from test.gui.fake_server_manager import FakeServerManager, ServerConfig
from typing import List

logging.basicConfig(level=logging.DEBUG)

register_thread(QT_THREAD_NAME)
app = QApplication([])
app.setStyleSheet(assets.load_text(["stylesheets", "scrutiny_base.qss"]))

window = QMainWindow()
central_widget = QWidget()
window.setCentralWidget(central_widget)

registry = WatchableRegistry()
server_manager = FakeServerManager(registry)
server_manager.start(ServerConfig('localhost', 1234))
server_manager.simulate_server_connect()
server_manager.simulate_sfd_loaded()
server_manager.simulate_device_ready()

varlist = VarListComponent(main_window=window, instance_name="varlist1", server_manager=server_manager, watchable_registry=registry)
watch1 = WatchComponent(main_window=window, instance_name="watch1", server_manager=server_manager, watchable_registry=registry)
model = GraphSignalModel(window)
graph_axes_zone = GraphSignalTree(window, model)

varlist.setup()
watch1.setup()

layout = QHBoxLayout(central_widget)
layout.addWidget(varlist)
layout.addWidget(watch1)
layout.addWidget(graph_axes_zone)

window.show()

sys.exit(app.exec())
