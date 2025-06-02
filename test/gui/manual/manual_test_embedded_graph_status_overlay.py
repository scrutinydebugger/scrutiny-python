#    manual_test_embedded_graph_status_overlay.py
#        A manual test suite that validates how the embedded graph status overlay behaves
#        with resizes
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

if __name__ != '__main__' : 
    raise RuntimeError("This script is expected to run from the command line")

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from manual_test_base import make_manual_test_app
app = make_manual_test_app()

from PySide6.QtWidgets import QMainWindow, QWidget,  QVBoxLayout, QHBoxLayout, QGraphicsScene, QGraphicsRectItem, QGraphicsView, QPushButton, QLineEdit, QComboBox
from PySide6.QtCore import QRect, QObject, Signal, QPoint
from scrutiny.gui.components.locals.embedded_graph.chart_status_overlay import ChartStatusOverlay
from scrutiny.gui import assets

class WindowWithResizeSignal(QMainWindow):

    class _Signals(QObject):
        resized = Signal()

    signals:_Signals
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.signals = self._Signals()

    def resizeEvent(self, event):
        self.signals.resized.emit()
        return super().resizeEvent(event)

window = WindowWithResizeSignal()
central_widget = QWidget()
window.setCentralWidget(central_widget)

scene = QGraphicsScene()
view = QGraphicsView(scene)
container = QGraphicsRectItem(QRect(0,0,800,600))
overlay = ChartStatusOverlay(container)

scene.addItem(container)
view.setContentsMargins(0,0,0,0)
view.show()

btn_apply = QPushButton("Apply")
txt_text = QLineEdit()
cmb_icon = QComboBox()
cmb_icon.addItem("None", None)
cmb_icon.addItem("Square", assets.Icons.TestSquare)
cmb_icon.addItem("VRrect", assets.Icons.TestVRect)
cmb_icon.addItem("Hrect", assets.Icons.TestHRect)

widget_line = QWidget()
widget_line_layout = QHBoxLayout(widget_line)
widget_line_layout.addWidget(txt_text)
widget_line_layout.addWidget(cmb_icon)
widget_line_layout.addWidget(btn_apply)
def apply():
    icon = cmb_icon.currentData()
    overlay.set(icon, txt_text.text())
btn_apply.clicked.connect(apply)

layout = QVBoxLayout(central_widget)
layout.addWidget(widget_line)
layout.addWidget(view)

window.show()

def handle_resize():
    container.prepareGeometryChange()
    container.setRect(QRect(QPoint(0,0), view.size()*0.8))
    container.update()

handle_resize()
window.signals.resized.connect(handle_resize)


sys.exit(app.exec())
