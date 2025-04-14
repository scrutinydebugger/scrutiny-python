
__all__ = [
    'ScrutinyThemeProperties',
    'ScrutinyTheme',
    'get_theme',
    'set_theme',
]

import enum
from typing import Any
import abc
from typing import Optional


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
    
    @abc.abstractmethod
    def get_val(self, prop:ScrutinyThemeProperties) -> Any:
        pass

_loaded_theme:Optional[ScrutinyTheme] = None

def get_theme() -> ScrutinyTheme:
    global _loaded_theme
    assert _loaded_theme is not None # Require a call to set theme first
    return _loaded_theme

def get_theme_prop(prop:ScrutinyThemeProperties)-> Any:
    return get_theme().get_val(prop)

def set_theme(theme:ScrutinyTheme) -> None:
    global _loaded_theme
    _loaded_theme = theme
