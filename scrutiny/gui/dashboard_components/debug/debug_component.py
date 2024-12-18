#    debug_component.py
#        A component used to develop the GUI
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from typing import Dict,Any

from PySide6.QtWidgets import QFormLayout, QLabel,  QTextEdit
from PySide6.QtCore import QMimeData,  QTimer
from scrutiny.gui.dashboard_components.common.watchable_line_edit import WatchableLineEdit
from scrutiny.gui.widgets.app_stats_display import ApplicationStatsDisplay
from scrutiny.gui import assets

class DroppableTextEdit(QTextEdit):
    def __init__(self, *args:Any, **kwargs:Any) -> None:
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)

    def canInsertFromMimeData(self, source: QMimeData) -> bool:
        return source.hasFormat('application/json')
    
    def insertFromMimeData(self, source: QMimeData) -> None:
        self.setText(source.data('application/json').toStdString())

class DebugComponent(ScrutinyGUIBaseComponent):
    _ICON = assets.get("debug-96x128.png")
    _NAME = "Debug"

    _label_nb_status_update:QLabel
    _nb_status_update:int
    _watchable_line_edit:WatchableLineEdit
    _dnd_text_edit:DroppableTextEdit



    def setup(self) -> None:
        layout = QFormLayout(self)
        self._nb_status_update = 0
        self._watchable_line_edit = WatchableLineEdit()
        self._watchable_line_edit.setMaximumWidth(100)
        self._dnd_text_edit = DroppableTextEdit()
        self._dnd_text_edit.setMaximumSize(400,300)
        self.app_stats = ApplicationStatsDisplay(self)


        layout.addRow(QLabel("Component name:"), QLabel(self._NAME))
        layout.addRow(QLabel("Instance name:"), QLabel(self.instance_name))
        layout.addRow(QLabel("Droppable line edit:"), self._watchable_line_edit)
        layout.addRow(QLabel("Drag & Drop zone:"), self._dnd_text_edit)
        layout.addRow(QLabel("stats:"), self.app_stats)
        
        self.timer = QTimer()
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.stats_timer_timeout)
        self.timer.start()

    def stats_timer_timeout(self) -> None:
        self.app_stats.update_data(self.server_manager.get_stats())

    def teardown(self) -> None:
        pass

    def get_state(self) -> Dict[Any, Any]:
        return {}

    def load_state(self, state:Dict[Any, Any]) -> None:
        pass
