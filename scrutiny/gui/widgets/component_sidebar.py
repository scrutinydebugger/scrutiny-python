#    component_sidebar.py
#        The sidebar with the dashboard component that can be added
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

__all__ = ['ComponentSidebar']


import functools

from PySide6.QtWidgets import QToolBar, QToolButton, QSizePolicy
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QAction

from scrutiny.gui.components.locals.base_local_component import ScrutinyGUIBaseLocalComponent
from scrutiny.gui.components.globals.base_global_component import ScrutinyGUIBaseGlobalComponent

from scrutiny.tools.typing import *


class ComponentSidebar(QToolBar):
    insert_local_component = Signal(type)
    show_global_component = Signal(type)

    def __init__(self,
                 global_components: List[Type[ScrutinyGUIBaseGlobalComponent]],
                 local_components: List[Type[ScrutinyGUIBaseLocalComponent]]) -> None:
        super().__init__()

        self.setIconSize(QSize(32, 24))

        for global_component in global_components:
            btn = QToolButton(self)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed))

            btn_action = QAction(global_component.get_icon(), global_component.get_name().replace(' ', '\n'), self)
            btn_action.triggered.connect(functools.partial(self.trigger_show_global_signal, global_component))

            btn.addAction(btn_action)
            btn.setDefaultAction(btn_action)
            self.addWidget(btn)

        self.addSeparator()

        for local_component in local_components:
            btn = QToolButton(self)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed))

            btn_action = QAction(local_component.get_icon(), local_component.get_name().replace(' ', '\n'), self)
            btn_action.triggered.connect(functools.partial(self.trigger_insert_local_signal, local_component))

            btn.addAction(btn_action)
            btn.setDefaultAction(btn_action)
            self.addWidget(btn)

    def trigger_insert_local_signal(self, component: Type[ScrutinyGUIBaseLocalComponent]) -> None:
        self.insert_local_component.emit(component)

    def trigger_show_global_signal(self, component: Type[ScrutinyGUIBaseGlobalComponent]) -> None:
        self.show_global_component.emit(component)
