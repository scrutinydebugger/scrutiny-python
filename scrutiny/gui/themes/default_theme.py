#    default_theme.py
#        A color theme that serves as a base for other theme and loaded by default
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny.gui.themes import ScrutinyTheme, ScrutinyThemeProperties
from PySide6.QtGui import QColor

from typing import Any

class DefaultTheme(ScrutinyTheme):

    RED_ERROR = QColor(255,0,0)

    prop_dict = {
        ScrutinyThemeProperties.CHART_NORMAL_SERIES_WIDTH : 2,
        ScrutinyThemeProperties.CHART_EMPHASIZED_SERIES_WIDTH : 3,
        ScrutinyThemeProperties.CHART_CALLOUT_MARKER_RADIUS : 5,
        ScrutinyThemeProperties.WIDGET_ERROR_BACKGROUND_COLOR : RED_ERROR,
    }

    def get_val(self, prop:ScrutinyThemeProperties) -> Any:
        return self.prop_dict[prop]
        
