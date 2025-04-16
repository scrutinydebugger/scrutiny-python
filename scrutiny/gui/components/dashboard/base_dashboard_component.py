#    base_dashboard_component.py
#        A base class for a component that can be added to the dashboard
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['ScrutinyGUIBaseDashboardComponent']

from abc import ABC, abstractmethod

from typing import Dict, Any

from scrutiny.gui.components.base_component import ScrutinyGUIBaseComponent

class ScrutinyGUIBaseDashboardComponent(ScrutinyGUIBaseComponent):
    
    @abstractmethod
    def get_state(self) -> Dict[Any, Any]:
        pass

    @abstractmethod
    def load_state(self, state:Dict[Any, Any]) -> None:
        pass
