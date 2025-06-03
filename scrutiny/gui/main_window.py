#    main_window.py
#        The QT Main window object
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

__all__ = ['MainWindow']

import logging
from pathlib import Path

from PySide6.QtWidgets import QWidget, QHBoxLayout
from PySide6.QtGui import QCloseEvent
from PySide6.QtCore import Qt, QRect
from PySide6.QtWidgets import QMainWindow

from scrutiny.gui.core.persistent_data import gui_persistent_data
from scrutiny.gui.core.local_server_runner import LocalServerRunner
from scrutiny.gui.app_settings import app_settings
from scrutiny.gui.tools.invoker import invoke_later
from scrutiny.gui.tools import prompt

from scrutiny.gui.dialogs.about_dialog import AboutDialog
from scrutiny.gui.widgets.component_sidebar import ComponentSidebar
from scrutiny.gui.widgets.status_bar import StatusBar
from scrutiny.gui.widgets.menu_bar import MenuBar
from scrutiny.gui.dialogs.server_config_dialog import ServerConfigDialog
from scrutiny.gui.dashboard.dashboard import Dashboard

from scrutiny.gui.components.locals.base_local_component import ScrutinyGUIBaseLocalComponent
from scrutiny.gui.components.globals.base_global_component import ScrutinyGUIBaseGlobalComponent
from scrutiny.gui.components.globals.varlist.varlist_component import VarListComponent
from scrutiny.gui.components.locals.watch.watch_component import WatchComponent
from scrutiny.gui.components.locals.continuous_graph.continuous_graph_component import ContinuousGraphComponent
from scrutiny.gui.components.locals.embedded_graph.embedded_graph_component import EmbeddedGraphComponent
from scrutiny.gui.components.globals.metrics.metrics_component import MetricsComponent

from scrutiny.gui.core.server_manager import ServerManager
from scrutiny.gui.core.watchable_registry import WatchableRegistry

from scrutiny.tools.typing import *


class MainWindow(QMainWindow):
    INITIAL_W = 1200
    INITIAL_H = 900

    ENABLED_GLOBALS_COMPONENTS: List[Type[ScrutinyGUIBaseGlobalComponent]] = [
        VarListComponent,
        MetricsComponent
    ]

    ENABLED_LOCAL_COMPONENTS: List[Type[ScrutinyGUIBaseLocalComponent]] = [
        WatchComponent,
        ContinuousGraphComponent,
        EmbeddedGraphComponent
    ]

    _logger: logging.Logger

    _central_widget: QWidget

    _component_sidebar: ComponentSidebar
    _server_config_dialog: ServerConfigDialog
    _watchable_registry: WatchableRegistry
    _server_manager: ServerManager
    _menu_bar: MenuBar
    _status_bar: StatusBar
    _dashboard: Dashboard
    _local_server_runner: LocalServerRunner

    def __init__(self) -> None:
        super().__init__()

        self._logger = logging.getLogger(self.__class__.__name__)

        self.setWindowTitle('Scrutiny Debugger')
        self.setGeometry(self.centered(self.INITIAL_W, self.INITIAL_H))
        self.setWindowState(Qt.WindowState.WindowMaximized)

        self._watchable_registry = WatchableRegistry()
        self._server_manager = ServerManager(watchable_registry=self._watchable_registry)
        self._dashboard = Dashboard(self)
        self._local_server_runner = LocalServerRunner()

        self._make_main_zone()

        self._status_bar = StatusBar(self, server_manager=self._server_manager, local_server_runner=self._local_server_runner)
        self.setStatusBar(self._status_bar)

        self._menu_bar = MenuBar()
        self.setMenuBar(self._menu_bar)

        self._menu_bar.signals.info_about_click.connect(self.show_about)
        self._menu_bar.signals.dashboard_clear_click.connect(self._dashboard_clear_click)
        self._menu_bar.signals.dashboard_save_click.connect(self._dashboard_save_click)
        self._menu_bar.signals.dashboard_save_as_click.connect(self._dashboard_save_as_click)
        self._menu_bar.signals.dashboard_open_click.connect(self._dashboard_open_click)
        self._menu_bar.signals.dashboard_recent_open.connect(self._dashboard_recent_open_click)

        self._menu_bar.set_dashboard_recents(self._dashboard.read_history())

        server_config_dialog = self._status_bar.get_server_config_dialog()

        if app_settings().start_local_server:
            port = app_settings().local_server_port
            server_config_dialog.set_local_server_port(port)
            server_config_dialog.set_server_type(ServerConfigDialog.ServerType.LOCAL)

            def start_local_server() -> None:
                self._local_server_runner.start(port)
            invoke_later(start_local_server)

        if app_settings().auto_connect:
            invoke_later(self.start_server_manager)

    def centered(self, w: int, h: int) -> QRect:
        """Returns a rectangle centered in the screen of given width/height"""
        screen = self.screen()
        assert screen is not None
        return QRect(
            max((screen.geometry().width() - w), 0) // 2,
            max((screen.geometry().height() - h), 0) // 2,
            w, h)

    def show_about(self) -> None:
        dialog = AboutDialog(self)
        dialog.setGeometry(self.centered(400, 200))
        dialog.show()

    def _make_main_zone(self) -> None:
        self._central_widget = QWidget()
        self._central_widget.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(self._central_widget)

        hlayout = QHBoxLayout(self._central_widget)
        hlayout.setContentsMargins(0, 0, 0, 0)
        hlayout.setSpacing(0)

        self._component_sidebar = ComponentSidebar(
            global_components=self.ENABLED_GLOBALS_COMPONENTS,
            local_components=self.ENABLED_LOCAL_COMPONENTS
        )
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self._component_sidebar)

        self._component_sidebar.insert_local_component.connect(self._dashboard.add_local_component)
        self._component_sidebar.show_global_component.connect(self._dashboard.create_or_show_global_component)

        hlayout.addWidget(self._dashboard)
        self._dashboard.make_default_dashboard()

        self._dashboard.signals.active_file_changed.connect(self._dashboard_active_file_changed_slot)

    def start_server_manager(self) -> None:
        """Start the server manager by emulating a click to the "connect" button """
        self._status_bar.update_content()  # Make sure the connect button is enabled if it can
        self._status_bar.emulate_connect_click()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._server_manager.exit()
        self._watchable_registry.clear()
        self._dashboard.exit()
        self._local_server_runner.stop()
        gui_persistent_data.save()  # Not supposed to raise
        super().closeEvent(event)

    def _dashboard_clear_click(self) -> None:
        self._dashboard.make_default_dashboard()

    def _dashboard_save_click(self) -> None:
        self._dashboard.save_active_or_prompt()

    def _dashboard_save_as_click(self) -> None:
        self._dashboard.save_with_prompt()

    def _save_before_open_question(self) -> None:
        if self._dashboard.local_components_count() > 0:
            require_save = prompt.yes_no_question(self, "Do you want to save the actual dashboard?", "Save?")
            if require_save:
                self._dashboard.save_with_prompt()

    def _dashboard_open_click(self) -> None:
        self._save_before_open_question()
        self._dashboard.open_with_prompt()

    def _dashboard_recent_open_click(self, filepath: str) -> None:
        self._save_before_open_question()
        self._dashboard.open(Path(filepath))

    def get_server_manager(self) -> ServerManager:
        return self._server_manager

    def get_watchable_registry(self) -> WatchableRegistry:
        return self._watchable_registry

    def _dashboard_active_file_changed_slot(self) -> None:
        file = self._dashboard.get_active_file()
        if file is None:
            self.setWindowTitle("")
        else:
            self.setWindowTitle(file.name)

        self._menu_bar.set_dashboard_recents(self._dashboard.read_history())
