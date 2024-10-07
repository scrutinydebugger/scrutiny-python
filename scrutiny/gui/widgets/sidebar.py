#    sidebar.py
#        The GUI sidebar
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['Sidebar']


from qtpy.QtWidgets import QWidget,  QToolBar,  QAction, QToolButton, QSizePolicy
from qtpy.QtCore import Qt, QSize, Signal, QEvent
from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
import functools

from typing import List, Type, Dict

class Sidebar(QToolBar):
    _sidebar_elements:Dict[Type[ScrutinyGUIBaseComponent], QWidget]

    insert_component=Signal(type)

    def __init__(self, components:List[Type[ScrutinyGUIBaseComponent]]) -> None:
        super().__init__()

        self.setIconSize(QSize(32,24))       
        
        for component in components:
            btn = QToolButton(self)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed))
        
            btn_action = QAction(component.get_icon(), component.get_name().replace(' ', '\n'), self)

            btn_action.triggered.connect( functools.partial(self.trigger_signal, component))

            btn.addAction(btn_action)
            btn.setDefaultAction(btn_action)
            self.addWidget(btn)
    
    def trigger_signal(self, component:Type[ScrutinyGUIBaseComponent], event: QEvent) -> None:
        self.insert_component.emit(component)
