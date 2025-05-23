#    fusion_theme.py
#        A ScrutinyTheme that wraps the QT Fusion Style
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny.gui.themes import ScrutinyTheme, ScrutinyThemeProperties
from scrutiny.gui.themes.default_theme import DefaultTheme
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import QStyleFactory
from PySide6.QtCore import Qt
from scrutiny.tools.typing import *
from scrutiny.gui import assets

from typing import Any

LIGHT_HOVERED_COLOR = QColor(229, 243, 255)
LIGHT_SELECTED_COLOR = QColor(205, 232, 255)
LIGHT_PRESSED_COLOR = LIGHT_SELECTED_COLOR
LIGHT_SELECTED_HOVERED_BORDER_COLOR = QColor(153, 209, 255)

class FusionTheme(ScrutinyTheme):

    _prop_dict:Dict[ScrutinyThemeProperties, Any]
    _default_theme:DefaultTheme

    def __init__(self) -> None:
        style = QStyleFactory.create("fusion")
        stylesheets:List[str] = []
        stylesheets.append( assets.load_stylesheet('scrutiny_base.qss') )
        stylesheets.append( assets.load_stylesheet('ads_base.qss') )
        if self.is_dark():
            stylesheets.append( assets.load_stylesheet('ads_dark.qss') )
        else:
            stylesheets.append( assets.load_stylesheet('ads_light.qss') )

        super().__init__(
            palette=style.standardPalette(),
            stylesheet='\n'.join(stylesheets),
            style = style,
            iconset= assets.IconSet.Dark if self.is_dark() else assets.IconSet.Light
        )
        self._default_theme = DefaultTheme()
        
        self._prop_dict = {}
        if self.is_dark():
            self._prop_dict[ScrutinyThemeProperties.CHART_CURSOR_COLOR] = QColor(255,60,60) # Light red
            self._prop_dict[ScrutinyThemeProperties.CHART_TOOLBAR_HOVERED_BUTTON_COLOR] =  self.palette().highlight().color().darker(150)
            self._prop_dict[ScrutinyThemeProperties.CHART_TOOLBAR_HOVERED_SELECTED_BORDER_COLOR] = self.palette().highlight().color().darker(200)
            self._prop_dict[ScrutinyThemeProperties.CHART_TOOLBAR_PRESSED_COLOR] = self.palette().highlight().color().darker(200)
            self._prop_dict[ScrutinyThemeProperties.CHART_TOOLBAR_SELECTED_COLOR] = self.palette().highlight().color()
        else:
            self._prop_dict[ScrutinyThemeProperties.CHART_CURSOR_COLOR] = QColor(255,0,0) # Strong red
            self._prop_dict[ScrutinyThemeProperties.CHART_TOOLBAR_HOVERED_BUTTON_COLOR] = LIGHT_HOVERED_COLOR
            self._prop_dict[ScrutinyThemeProperties.CHART_TOOLBAR_HOVERED_SELECTED_BORDER_COLOR] = LIGHT_SELECTED_HOVERED_BORDER_COLOR
            self._prop_dict[ScrutinyThemeProperties.CHART_TOOLBAR_PRESSED_COLOR] = LIGHT_PRESSED_COLOR
            self._prop_dict[ScrutinyThemeProperties.CHART_TOOLBAR_SELECTED_COLOR] = LIGHT_SELECTED_COLOR

        self._prop_dict[ScrutinyThemeProperties.WATCHABLE_LINE_EDIT_CLEAR_BTN_HOVER_COLOR] = self._prop_dict[ScrutinyThemeProperties.CHART_TOOLBAR_SELECTED_COLOR]
        self._prop_dict[ScrutinyThemeProperties.WATCHABLE_LINE_EDIT_CLEAR_BTN_PRESSED_COLOR] = self._prop_dict[ScrutinyThemeProperties.CHART_TOOLBAR_PRESSED_COLOR]

    
    def get_val(self, prop:ScrutinyThemeProperties) -> Any:

        if prop in self._prop_dict:
            return self._prop_dict[prop]
        return self._default_theme.get_val(prop)

    def is_dark(self) -> bool:
        return QGuiApplication.styleHints().colorScheme()  == Qt.ColorScheme.Dark

    def name(self) -> str:
        scheme = 'dark' if self.is_dark() else 'light'
        return f"QT Fusion ({scheme})"
