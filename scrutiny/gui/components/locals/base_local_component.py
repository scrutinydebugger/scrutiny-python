#    base_dashboard_component.py
#        A base class for a component that can be added to the dashboard
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['ScrutinyGUIBaseLocalComponent']

from abc import ABC, abstractmethod



from scrutiny.gui.components.base_component import ScrutinyGUIBaseComponent

class ScrutinyGUIBaseLocalComponent(ScrutinyGUIBaseComponent):
    pass
