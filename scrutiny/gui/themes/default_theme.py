
from scrutiny.gui.themes import ScrutinyTheme, ScrutinyThemeProperties
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import QStyle, QApplication
from PySide6.QtCore import Qt

from scrutiny.gui import assets

from typing import Any

HOVERED_COLOR = QColor(229, 243, 255)
SELECTED_COLOR = QColor(205, 232, 255)
PRESSED_COLOR = SELECTED_COLOR
SELECTED_HOVERED_BORDER_COLOR = QColor(153, 209, 255)

class DefaultTheme(ScrutinyTheme):

    RED_ERROR = QColor(255,0,0)

    prop_dict = {
        ScrutinyThemeProperties.CHART_NORMAL_SERIES_WIDTH : 2,
        ScrutinyThemeProperties.CHART_EMPHASIZED_SERIES_WIDTH : 3,
        ScrutinyThemeProperties.CHART_CALLOUT_MARKER_RADIUS : 4,
        ScrutinyThemeProperties.CHART_CURSOR_MARKER_RADIUS : 4,
        ScrutinyThemeProperties.CHART_CURSOR_COLOR : QColor(255,0,0),

        ScrutinyThemeProperties.CHART_TOOLBAR_HOVERED_BUTTON_COLOR : HOVERED_COLOR,
        ScrutinyThemeProperties.CHART_TOOLBAR_HOVERED_SELECTED_BORDER_COLOR : SELECTED_HOVERED_BORDER_COLOR,
        ScrutinyThemeProperties.CHART_TOOLBAR_PRESSED_COLOR : PRESSED_COLOR,
        ScrutinyThemeProperties.CHART_TOOLBAR_SELECTED_COLOR : SELECTED_COLOR,
        
        ScrutinyThemeProperties.WATCHABLE_LINE_EDIT_CLEAR_BTN_HOVER_COLOR : SELECTED_COLOR,
        ScrutinyThemeProperties.WATCHABLE_LINE_EDIT_CLEAR_BTN_PRESSED_COLOR : PRESSED_COLOR,

        ScrutinyThemeProperties.WIDGET_ERROR_BACKGROUND_COLOR : RED_ERROR

    }

    def __init__(self) -> None:
        base_stylesheet = assets.load_stylesheet('scrutiny_base.qss')
        ads_stylesheet = assets.load_stylesheet('ads_base.qss')
        ads_stylesheet_light = assets.load_stylesheet('ads_light.qss')
        super().__init__(
            palette=QGuiApplication.palette(),
            stylesheet=base_stylesheet + ads_stylesheet + ads_stylesheet_light,
            style = QApplication.style(),
            iconset=assets.IconSet.Dark if self.is_dark() else assets.IconSet.Light
        )

    def get_val(self, prop:ScrutinyThemeProperties) -> Any:
        return self.prop_dict[prop]
        
    def is_dark(self) -> bool:
        return False
