#    test_watch_component.py
#        A test suite for the Watch Component
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

from PySide6.QtWidgets import QWidget
from test.gui.fake_server_manager import FakeServerManager
from test.gui.base_gui_test import ScrutinyBaseGuiTest
from scrutiny.gui.components.locals.watch.watch_component import WatchComponent, WatchComponentTreeModel
from scrutiny.gui.core.watchable_registry import WatchableRegistry

from scrutiny.tools.typing import *


class MainWindowStub(QWidget):
    def __init__(self):
        super().__init__()
        self.registry = WatchableRegistry()
        self.server_manager = FakeServerManager(self.registry)

    def get_server_manager(self):
        return self.server_manager

    def get_watchable_registry(self):
        return self.registry


class TestWatchComponent(ScrutinyBaseGuiTest):
    def setUp(self):
        super().setUp()
        self.main_window = MainWindowStub()
        self.watch1 = WatchComponent(self.main_window, 'watch1', self.main_window.get_watchable_registry(), self.main_window.get_server_manager())
        self.watch1.setup()

    def tearDown(self):
        self.watch1.teardown()
        return super().tearDown()

    def test_column_order_state(self):
        colmap = self.watch1.get_column_logical_indexes_by_name()
        self.assertEqual(len(colmap), self.watch1.column_count() - 1)

        state = self.watch1.get_state()
        self.assertIn('cols', state)
        for col in ['value', 'type', 'enum']:
            self.assertIn(col, state['cols'])

        state['cols'] = ['enum', 'type', 'value']
        self.watch1.load_state(state)

        tree = self.watch1._tree
        self.assertEqual(tree.header().visualIndex(WatchComponentTreeModel.enum_col()), 1)
        self.assertEqual(tree.header().visualIndex(WatchComponentTreeModel.datatype_col()), 2)
        self.assertEqual(tree.header().visualIndex(WatchComponentTreeModel.value_col()), 3)

        state['cols'] = ['enum', 'value', 'type']
        self.watch1.load_state(state)
        self.assertEqual(tree.header().visualIndex(WatchComponentTreeModel.enum_col()), 1)
        self.assertEqual(tree.header().visualIndex(WatchComponentTreeModel.value_col()), 2)
        self.assertEqual(tree.header().visualIndex(WatchComponentTreeModel.datatype_col()), 3)
