
__all__ = [
    'ScrutinyThemeProperties',
    'ScrutinyTheme',
    'scrutiny_get_theme',
    'scrutiny_get_theme_prop',
    'scrutiny_set_theme',
]

import enum
from typing import Any
import abc
from typing import Optional

from PySide6.QtWidgets import QApplication, QStyle
from PySide6.QtGui import QPalette
from scrutiny.gui import assets


class ScrutinyThemeProperties(enum.Enum):
    CHART_NORMAL_SERIES_WIDTH=enum.auto()
    CHART_EMPHASIZED_SERIES_WIDTH=enum.auto()
    CHART_CALLOUT_MARKER_RADIUS=enum.auto()
    CHART_CURSOR_MARKER_RADIUS=enum.auto()
    CHART_CURSOR_COLOR = enum.auto()
    
    CHART_TOOLBAR_HOVERED_BUTTON_COLOR = enum.auto()
    CHART_TOOLBAR_HOVERED_SELECTED_BORDER_COLOR = enum.auto()
    CHART_TOOLBAR_SELECTED_COLOR = enum.auto()
    CHART_TOOLBAR_PRESSED_COLOR = enum.auto()

    WATCHABLE_LINE_EDIT_CLEAR_BTN_HOVER_COLOR = enum.auto()
    WATCHABLE_LINE_EDIT_CLEAR_BTN_PRESSED_COLOR = enum.auto()

    WIDGET_ERROR_BACKGROUND_COLOR=enum.auto()

class ScrutinyTheme(abc.ABC):
    
    _palette:QPalette
    _stylesheet:str
    _style:QStyle

    def __init__(self, style:QStyle, palette:QPalette, stylesheet:str) -> None:
        self._style = style
        self._palette = palette
        base_stylesheet =  assets.load_text(['stylesheets', 'scrutiny_base.qss'])
        self._stylesheet = base_stylesheet + stylesheet
    
    def apply_to_app(self, app:QApplication) -> None:
        app.setStyle(self._style)
        app.setPalette(self._palette)
        app.setStyleSheet(self._stylesheet)


    @abc.abstractmethod
    def get_val(self, prop:ScrutinyThemeProperties) -> Any:
        pass

_loaded_theme:Optional[ScrutinyTheme] = None

def scrutiny_get_theme() -> ScrutinyTheme:
    global _loaded_theme
    assert _loaded_theme is not None # Require a call to set theme first
    return _loaded_theme

def scrutiny_get_theme_prop(prop:ScrutinyThemeProperties)-> Any:
    return scrutiny_get_theme().get_val(prop)

def scrutiny_set_theme(theme:ScrutinyTheme) -> None:
    global _loaded_theme
    _loaded_theme = theme
    theme.apply_to_app(QApplication.instance())
