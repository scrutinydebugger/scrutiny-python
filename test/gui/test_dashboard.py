#    test_dashboard.py
#        A test suite that validate the dashboard logic
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

import os
import tempfile
from pathlib import Path

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QIcon

from test.gui.base_gui_test import ScrutinyBaseGuiTest
from test.gui.fake_server_manager import FakeServerManager
from scrutiny.gui.core.watchable_registry import WatchableRegistry
from scrutiny.tools.typing import *
from scrutiny.gui.dashboard.dashboard import Dashboard
from scrutiny.gui.app_settings import configure_unit_test_app_settings
from scrutiny.gui.gui import ScrutinyQtGUI, SupportedTheme

from scrutiny.gui.components.globals.base_global_component import ScrutinyGUIBaseGlobalComponent
from scrutiny.gui.components.locals.base_local_component import ScrutinyGUIBaseLocalComponent
from scrutiny.gui.components.base_component import ScrutinyGUIBaseComponent

import PySide6QtAds as QtAds


class StubbedComponent(ScrutinyGUIBaseComponent):
    setup_called:bool
    ready_called:bool
    teardown_called:bool
    state:Dict[Any, Any]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_called = False
        self.ready_called = False
        self.teardown_called = False
        self.state = {}

    def setup(self) -> None:
        self.setup_called = True

    def ready(self) -> None:
        self.ready_called = True

    def teardown(self) -> None:
        self.teardown_called = True

    def get_state(self) -> Dict[Any, Any]:
        return self.state

    def load_state(self, state:Dict[Any, Any]) -> bool:
        self.state = state



class StubbedGlobalComponent(StubbedComponent, ScrutinyGUIBaseGlobalComponent):
    _ICON = QIcon()
    _NAME = "Stubbed Global"
    _TYPE_ID = "stubbed_global"

class StubbedGlobalComponent2(StubbedComponent, ScrutinyGUIBaseGlobalComponent):
    _ICON = QIcon()
    _NAME = "Stubbed Global 2"
    _TYPE_ID = "stubbed_global2"

class StubbedLocalComponent(StubbedComponent, ScrutinyGUIBaseLocalComponent):
    _ICON = QIcon()
    _NAME = "Stubbed Local"
    _TYPE_ID = "stubbed_local"
    

class MainWindowStub(QWidget):
    def __init__(self):
        super().__init__()
        self.registry = WatchableRegistry()
        self.server_manager = FakeServerManager(self.registry)

    def get_server_manager(self):
        return self.server_manager
    
    def get_watchable_registry(self):
        return self.registry

class TestDashboard(ScrutinyBaseGuiTest):
    def setUp(self):
        super().setUp()
        settings = ScrutinyQtGUI.Settings(
            debug_layout=False,
            auto_connect=False,
            opengl_enabled=False,
            local_server_port=8765,
            start_local_server=False,
            theme=SupportedTheme.Default
        )
        configure_unit_test_app_settings(settings)
        self.main_window = MainWindowStub()

    def test_setup_teardown(self):
        dashboard = Dashboard(self.main_window)

        global_dock_widget = dashboard.create_or_show_global_component(StubbedGlobalComponent)
        self.assertIsNotNone(global_dock_widget)
        self.assertTrue(global_dock_widget.isAutoHide())   # Default location for global is autohide
        global_component = cast(StubbedGlobalComponent, global_dock_widget.widget())
        self.assertIsInstance(global_component, StubbedGlobalComponent)
        self.assertTrue(global_component.setup_called)
        self.assertFalse(global_component.teardown_called)
        self.process_events()
        self.assertTrue(global_component.ready_called)
        
        # Global ha a single instance
        global_dock_widget2 = dashboard.create_or_show_global_component(StubbedGlobalComponent)
        self.assertIs(global_dock_widget2, global_dock_widget)

        local_dock_widget1 = dashboard.add_local_component(StubbedLocalComponent)
        local_dock_widget2 = dashboard.add_local_component(StubbedLocalComponent)

        self.assertIsNotNone(local_dock_widget1)
        self.assertIsNotNone(local_dock_widget2)

        local_component1 = cast(StubbedLocalComponent, local_dock_widget1.widget())
        local_component2 = cast(StubbedLocalComponent, local_dock_widget2.widget())

        self.assertIsInstance(local_component1, StubbedLocalComponent)
        self.assertIsInstance(local_component2, StubbedLocalComponent)
        self.assertIsNot(local_component1, local_component2)
        self.assertNotEqual(local_component1.instance_name, local_component2.instance_name)

        self.assertTrue(local_component1.setup_called)
        self.assertTrue(local_component2.setup_called)
        self.assertFalse(local_component1.teardown_called)
        self.assertFalse(local_component2.teardown_called)

        self.process_events()

        self.assertTrue(local_component1.ready_called)
        self.assertTrue(local_component2.ready_called)

        dock_widget_map = dashboard.dock_manager().dockWidgetsMap()
        self.assertIn(global_component.instance_name, dock_widget_map)
        self.assertIs(dock_widget_map[global_component.instance_name], global_dock_widget)

        self.assertIn(local_component1.instance_name, dock_widget_map)
        self.assertIs(dock_widget_map[local_component1.instance_name], local_dock_widget1)

        self.assertIn(local_component2.instance_name, dock_widget_map)
        self.assertIs(dock_widget_map[local_component2.instance_name], local_dock_widget2)


        dashboard.dock_manager().removeDockWidget(local_dock_widget1)
        self.assertTrue(local_component1.teardown_called)
        self.assertFalse(local_component2.teardown_called)
        self.assertNotIn(local_component1.instance_name, dashboard.dock_manager().dockWidgetsMap())

        dashboard.dock_manager().removeDockWidget(local_dock_widget2)
        self.assertTrue(local_component2.teardown_called)
        self.assertNotIn(local_component2.instance_name, dashboard.dock_manager().dockWidgetsMap())

        self.assertEqual(len(dashboard.dock_manager().dockWidgetsMap()), 1) # Single global

        global_component.load_state({"aaa" : "bbb"})
        dashboard.dock_manager().removeDockWidget(global_dock_widget)
        self.assertTrue(global_component.teardown_called)
        self.assertEqual(len(dashboard.dock_manager().dockWidgetsMap()), 0)

        global_dock_widget3 = dashboard.create_or_show_global_component(StubbedGlobalComponent)
        self.assertIsNotNone(global_dock_widget3)
        global_component3 = cast(StubbedGlobalComponent, global_dock_widget3.widget())
        self.assertIsInstance(global_dock_widget3.widget(), StubbedGlobalComponent)
        self.assertNotIn("aaa", global_component3.get_state())  # Make sure the state from the deleted component is gone
    
    def test_clear(self):
        dashboard = Dashboard(self.main_window)
        dw1 = dashboard.add_local_component(StubbedLocalComponent)
        dw2 = dashboard.add_local_component(StubbedLocalComponent)
        dw3 = dashboard.add_local_component(StubbedLocalComponent)

        self.assertEqual(len(dashboard.dock_manager().dockWidgetsMap()), 3)
        for dw in [dw1, dw2, dw3]:
            self.assertFalse(cast(StubbedLocalComponent, dw.widget()).teardown_called)
        
        dashboard.clear()
        self.assertEqual(len(dashboard.dock_manager().dockWidgetsMap()), 0)
        
        for dw in [dw1, dw2, dw3]:
            self.assertTrue(cast(StubbedLocalComponent, dw.widget()).teardown_called)
        
    def test_save_reload(self):
        dashboard = Dashboard(self.main_window)


        #   ┌------┬-----┬-----┐
        #   |      |  1  |     |
        #   |      ├-----┤     |
        #   |  0   | 3,5 | 2,6 |
        #   |      ├-----┤     |
        #   |      |  4  |     |
        #   └------┴-----┴-----┘

        dw0 = dashboard.add_local_component(StubbedLocalComponent)
        dw1 = dashboard.add_local_component(StubbedLocalComponent)
        dw2 = dashboard.add_local_component(StubbedLocalComponent)
        dw3 = dashboard.add_local_component(StubbedLocalComponent)
        dw4 = dashboard.add_local_component(StubbedLocalComponent)
        dw5 = dashboard.add_local_component(StubbedLocalComponent)
        dw6 = dashboard.add_local_component(StubbedLocalComponent)

        dashboard.dock_manager().addDockWidget(QtAds.RightDockWidgetArea, dw1, dw0.dockAreaWidget())
        dashboard.dock_manager().addDockWidget(QtAds.RightDockWidgetArea, dw2, dw1.dockAreaWidget())
        dashboard.dock_manager().addDockWidget(QtAds.BottomDockWidgetArea, dw3, dw1.dockAreaWidget())
        dashboard.dock_manager().addDockWidget(QtAds.BottomDockWidgetArea, dw4, dw3.dockAreaWidget())
        dashboard.dock_manager().addDockWidget(QtAds.CenterDockWidgetArea, dw5, dw3.dockAreaWidget())
        dashboard.dock_manager().addDockWidget(QtAds.CenterDockWidgetArea, dw6, dw2.dockAreaWidget())
        
        dw6.setAsCurrentTab()
        dw3.setAsCurrentTab()
        

        dw7 = dashboard.add_local_component(StubbedLocalComponent)
        dw8 = dashboard.add_local_component(StubbedLocalComponent)
        dw9 = dashboard.add_local_component(StubbedLocalComponent)
        dw10 = dashboard.add_local_component(StubbedLocalComponent)
        dw11 = dashboard.add_local_component(StubbedLocalComponent)

        dashboard.dock_manager().addAutoHideDockWidget(QtAds.SideBarRight, dw7)
        dashboard.dock_manager().addAutoHideDockWidget(QtAds.SideBarRight, dw8)
        dashboard.dock_manager().addAutoHideDockWidget(QtAds.SideBarTop, dw9)
        dashboard.dock_manager().addAutoHideDockWidget(QtAds.SideBarBottom, dw10)
        dashboard.dock_manager().addAutoHideDockWidget(QtAds.SideBarLeft, dw11)

        dw12 = dashboard.add_local_component(StubbedLocalComponent)
        dw13 = dashboard.add_local_component(StubbedLocalComponent)
        dw14 = dashboard.add_local_component(StubbedLocalComponent)
        dw15 = dashboard.add_local_component(StubbedLocalComponent)

        #   ┌---------------┐
        #   |     14,15     |
        #   ├---------------┤  
        #   |      13       |
        #   ├---------------┤ 
        #   |      12       |
        #   └---------------┘

        floating1 = dashboard.dock_manager().addDockWidgetFloating(dw12)
        dashboard.dock_manager().addDockWidget(QtAds.TopDockWidgetArea, dw13, dw12.dockAreaWidget())
        dashboard.dock_manager().addDockWidget(QtAds.TopDockWidgetArea, dw14, dw13.dockAreaWidget())
        dashboard.dock_manager().addDockWidget(QtAds.CenterDockWidgetArea, dw15, dw14.dockAreaWidget())
        dw14.setAsCurrentTab()

        dw16 = dashboard.add_local_component(StubbedLocalComponent)
        dw17 = dashboard.add_local_component(StubbedLocalComponent)
        dashboard.dock_manager().addAutoHideDockWidgetToContainer(QtAds.SideBarRight, dw16, floating1.dockContainer())
        dashboard.dock_manager().addAutoHideDockWidgetToContainer(QtAds.SideBarRight, dw17, floating1.dockContainer())
        
        all_dock_widgets = [dw0, dw1, dw2, dw3, dw4, dw5, dw6, dw7, dw8, dw9, dw10, dw11, dw12, dw13,dw14,dw15,dw16,dw17]

        for dw in all_dock_widgets:
            component = cast(StubbedLocalComponent, dw.widget())
            component.load_state({"original_instance_name" : component.instance_name})
        
        # Create a new dashboard from previous dashboard. State of first dashboard should be transferred to the new one
        new_dashboard = Dashboard(self.main_window)
        self.assertEqual(len(new_dashboard.dock_manager().dockWidgetsMap()), 0)
        with tempfile.TemporaryDirectory() as d:
            file = Path(os.path.join(d, 'test_dashboard'))
            dashboard.save(file)
            new_dashboard.open(file, exceptions=True)
        
        # New dashboard is reloaded from file. Check that it matches the original one.
        self.assertEqual(len(new_dashboard.dock_manager().dockWidgetsMap()), len(all_dock_widgets))
        containers = new_dashboard.dock_manager().dockContainers()
        floating_containers = [c for c in containers if c.isFloating()]     # extra window
        normal_containers = [c for c in containers if not c.isFloating()]   # Main window
        self.assertEqual(len(containers), 2)
        self.assertEqual(len(floating_containers), 1)
        self.assertEqual(len(normal_containers), 1)

        new_main_container = normal_containers[0]
        new_floating_container = floating_containers[0]


        #  ---- main window ----
        #       Main window Split pane
        main_splitpane_widgets = new_main_container.openedDockWidgets()
        self.assertEqual(len(main_splitpane_widgets), 7) # 0-6
        main_splitpane_components = [cast(StubbedLocalComponent, x.widget()) for x in main_splitpane_widgets]
        main_splitpane_instance_names = [x.get_state()['original_instance_name'] for x in main_splitpane_components]
        for dw in [dw0, dw1, dw2, dw3, dw4, dw5, dw6]:
            self.assertIn(cast(StubbedLocalComponent, dw.widget()).instance_name, main_splitpane_instance_names)

        #       Main window Autohide
        main_autohides = new_main_container.autoHideWidgets()
        self.assertEqual(len(main_autohides), 5) # 7-11
        autohide_components = [cast(StubbedLocalComponent, x.dockWidget().widget()) for x in main_autohides]
        autohide_instance_names = [x.get_state()['original_instance_name'] for x in autohide_components]

        for dw in [dw7, dw8, dw9, dw10, dw11]:
            self.assertIn(cast(StubbedLocalComponent, dw.widget()).instance_name, autohide_instance_names)


        #  ---- 2nd window ----
        #       2nd window Split pane
        floating_splitpane_widgets = new_floating_container.openedDockWidgets()
        self.assertEqual(len(floating_splitpane_widgets), 4) # 12-15
        floating_splitpane_components = [cast(StubbedLocalComponent, x.widget()) for x in floating_splitpane_widgets]
        floating_splitpane_instance_names = [x.get_state()['original_instance_name'] for x in floating_splitpane_components]
        for dw in [dw12, dw13, dw14, dw15]:
            self.assertIn(cast(StubbedLocalComponent, dw.widget()).instance_name, floating_splitpane_instance_names)        
        
        #       2nd window autohide
        floating_autohide = new_floating_container.autoHideWidgets()
        self.assertEqual(len(floating_autohide), 2) # 16, 17
        autohide_components = [cast(StubbedLocalComponent, x.dockWidget().widget()) for x in floating_autohide]
        autohide_instance_names = [x.get_state()['original_instance_name'] for x in autohide_components]
        for dw in [dw16, dw17]:
            self.assertIn(cast(StubbedLocalComponent, dw.widget()).instance_name, autohide_instance_names)


        def find_new_dw(old_dw:QtAds.CDockWidget) -> QtAds.CDockWidget:
            for name, dw in new_dashboard.dock_manager().dockWidgetsMap().items():
                old_component = cast(StubbedLocalComponent, old_dw.widget())
                component = cast(StubbedLocalComponent, dw.widget())

                if component.get_state()['original_instance_name'] == old_component.instance_name:
                    return dw
            
            raise KeyError("Dock widget not found")
        
        
        new_dw = [find_new_dw(dw) for dw in all_dock_widgets]
        # Check the layout. Check on both old and new dashboard to make sure they are identical
        for dw_set in (all_dock_widgets, new_dw):
            if dw_set is all_dock_widgets:
                subtest_name = "Original dashboard"
            elif dw_set is new_dw:
                subtest_name = "New dashboard"
            else:
                raise RuntimeError()
            
            with self.subTest(subtest_name):
                # Tabs check
                self.assertTrue(dw_set[2].isTabbed())
                self.assertTrue(dw_set[6].isTabbed())
                self.assertIs(dw_set[2].dockAreaWidget(), dw_set[6].dockAreaWidget())
                self.assertFalse(dw_set[2].isCurrentTab())
                self.assertTrue(dw_set[6].isCurrentTab())

                self.assertTrue(dw_set[3].isTabbed())
                self.assertTrue(dw_set[5].isTabbed())
                self.assertIs(dw_set[3].dockAreaWidget(), dw_set[5].dockAreaWidget())
                self.assertFalse(dw_set[5].isCurrentTab())
                self.assertTrue(dw_set[3].isCurrentTab())

                self.assertTrue(dw_set[14].isTabbed())
                self.assertTrue(dw_set[15].isTabbed())
                self.assertIs(dw_set[14].dockAreaWidget(), dw_set[15].dockAreaWidget())
                self.assertFalse(dw_set[15].isCurrentTab())
                self.assertTrue(dw_set[14].isCurrentTab())

                # Make sure we have 2 containers (windows) and dock widget are owned by the correct one
                self.assertIsNot(dw_set[0].dockContainer(), dw_set[12].dockContainer())
                for i in range(0,12):   # Main
                    self.assertIs(dw_set[0].dockContainer(), dw_set[i].dockContainer())

                for i in range(12,18):  # Floating
                    self.assertIs(dw_set[12].dockContainer(), dw_set[i].dockContainer())
                
                # main Split pane
                self.assertIs(dw_set[0].dockAreaWidget().parent().parent(), dw_set[0].dockContainer().rootSplitter())   
                
                self.assertIsInstance(dw_set[1].dockAreaWidget().parent(), QtAds.CDockSplitter)
                self.assertIs(dw_set[1].dockAreaWidget().parent(), dw_set[3].dockAreaWidget().parent())
                self.assertIs(dw_set[1].dockAreaWidget().parent(), dw_set[5].dockAreaWidget().parent())
                self.assertIs(dw_set[1].dockAreaWidget().parent(), dw_set[4].dockAreaWidget().parent())

                self.assertIsInstance(dw_set[0].dockAreaWidget().parent(), QtAds.CDockSplitter)
                self.assertIs(dw_set[0].dockAreaWidget().parent(), dw_set[2].dockAreaWidget().parent())
                self.assertIs(dw_set[0].dockAreaWidget().parent(), dw_set[6].dockAreaWidget().parent())
                self.assertIs(dw_set[0].dockAreaWidget().parent(), dw_set[1].dockAreaWidget().parent().parent())                
                

                self.assertIs(dw_set[12].dockAreaWidget().parent(), dw_set[13].dockAreaWidget().parent())
                self.assertIs(dw_set[12].dockAreaWidget().parent(), dw_set[14].dockAreaWidget().parent())
                self.assertIs(dw_set[12].dockAreaWidget().parent(), dw_set[15].dockAreaWidget().parent())
                
                self.assertIs(dw_set[12].dockAreaWidget().parent(), dw_set[12].dockContainer().rootSplitter())

    def test_make_default_dashboard(self):
        dashboard = Dashboard(self.main_window)
        dashboard.make_default_dashboard()
        self.assertGreater(len(dashboard.dock_manager().dockWidgetsMap()), 0)  # Creating a default dashboard created something. 

    def test_show_global_component_that_was_moved(self):
        dashboard = Dashboard(self.main_window)
        local_dw = dashboard.add_local_component(StubbedLocalComponent)
        dashboard.dock_manager().addDockWidgetTab(QtAds.CenterDockWidgetArea, local_dw)
        dock_widget1 = dashboard.create_or_show_global_component(StubbedGlobalComponent)
        dock_widget2 = dashboard.create_or_show_global_component(StubbedGlobalComponent2)
        dashboard.dock_manager().addDockWidgetFloating(dock_widget1)
        dock_widget3 = dashboard.create_or_show_global_component(StubbedGlobalComponent)

        self.assertIs(dock_widget1, dock_widget3)
        self.assertTrue(dock_widget3.isFloating())
        self.assertFalse(dock_widget1.dockAreaWidget().isAutoHide())    # Bug #739. check dockarea instead of dock_widget.isAutoHide

        dashboard.dock_manager().addDockWidgetTab(QtAds.CenterDockWidgetArea, dock_widget2)
        dock_widget4 = dashboard.create_or_show_global_component(StubbedGlobalComponent2)

        self.assertIs(dock_widget2, dock_widget4)
        self.assertFalse(dock_widget2.isFloating())
        self.assertFalse(dock_widget2.dockAreaWidget().isAutoHide()) 
        self.assertTrue(dock_widget2.isTabbed())    # Share tab with local component

    def test_ads_bug_739(self):
        QtAds.CDockManager.setAutoHideConfigFlags(QtAds.CDockManager.DefaultAutoHideConfig)
        dock_conainer = QWidget()
        dock_manager = QtAds.CDockManager(dock_conainer)
        dock_widget = QtAds.CDockWidget("foo", dock_manager)
        dock_manager.addAutoHideDockWidget(QtAds.SideBarRight, dock_widget)
        self.assertFalse(dock_widget.isFloating())
        self.assertTrue(dock_widget.isAutoHide())
        dock_manager.addDockWidgetFloating(dock_widget)
        self.assertTrue(dock_widget.isFloating())   # This is fine
        self.assertFalse(dock_widget.dockAreaWidget().isAutoHide())  # This is fine
       # self.assertFalse(dock_widget.isAutoHide())  # This fails!
