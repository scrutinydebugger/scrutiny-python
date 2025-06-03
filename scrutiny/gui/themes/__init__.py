
__all__ = [
    'ScrutinyThemeProperties',
    'ScrutinyTheme',
    'scrutiny_get_theme',
    'scrutiny_get_theme_prop',
    'scrutiny_set_theme',
]

import enum
import abc

from PySide6.QtWidgets import QApplication, QStyle, QWidget
from PySide6.QtGui import QPalette, QIcon, QPixmap
from scrutiny.gui import assets
from scrutiny.tools.typing import *


class ScrutinyThemeProperties(enum.Enum):
    CHART_NORMAL_SERIES_WIDTH = enum.auto()
    CHART_EMPHASIZED_SERIES_WIDTH = enum.auto()
    CHART_CALLOUT_MARKER_RADIUS = enum.auto()
    CHART_CURSOR_MARKER_RADIUS = enum.auto()
    CHART_CURSOR_COLOR = enum.auto()

    CHART_TOOLBAR_HOVERED_BUTTON_COLOR = enum.auto()
    CHART_TOOLBAR_HOVERED_SELECTED_BORDER_COLOR = enum.auto()
    CHART_TOOLBAR_SELECTED_COLOR = enum.auto()
    CHART_TOOLBAR_PRESSED_COLOR = enum.auto()

    WATCHABLE_LINE_EDIT_CLEAR_BTN_HOVER_COLOR = enum.auto()
    WATCHABLE_LINE_EDIT_CLEAR_BTN_PRESSED_COLOR = enum.auto()

    WIDGET_ERROR_BACKGROUND_COLOR = enum.auto()


class ScrutinyTheme(abc.ABC):
    STATE_PROPERTY = "state"

    _palette: QPalette
    _stylesheet: str
    _style: QStyle
    _iconset: assets.IconSet

    def __init__(self, style: QStyle, palette: QPalette, stylesheet: str, iconset: assets.IconSet) -> None:
        self._style = style
        self._palette = palette
        self._stylesheet = stylesheet
        self._iconset = iconset

    def apply_to_app(self, app: QApplication) -> None:
        app.setStyle(self._style)
        app.setPalette(self._palette)
        app.setStyleSheet(self._stylesheet)

    def iconset(self) -> assets.IconSet:
        return self._iconset

    def palette(self) -> QPalette:
        return self._palette

    def load_tiny_icon(self, icon: assets.Icons) -> QIcon:
        return assets.load_icon(icon, assets.IconFormat.Tiny, self._iconset)

    def load_medium_icon(self, icon: assets.Icons) -> QIcon:
        return assets.load_icon(icon, assets.IconFormat.Medium, self._iconset)

    def load_large_icon(self, icon: assets.Icons) -> QIcon:
        return assets.load_icon(icon, assets.IconFormat.Large, self._iconset)

    def load_tiny_icon_as_pixmap(self, name: assets.Icons) -> QPixmap:
        return assets.load_icon_as_pixmap(name, assets.IconFormat.Tiny, self._iconset)

    def load_medium_icon_as_pixmap(self, name: assets.Icons) -> QPixmap:
        return assets.load_icon_as_pixmap(name, assets.IconFormat.Medium, self._iconset)

    def load_large_icon_as_pixmap(self, name: assets.Icons) -> QPixmap:
        return assets.load_icon_as_pixmap(name, assets.IconFormat.Large, self._iconset)

    def set_state(self, widget: QWidget, value: str) -> None:
        previous = widget.property(self.STATE_PROPERTY)
        widget.setProperty(self.STATE_PROPERTY, value)
        if value != previous:
            style = widget.style()
            style.unpolish(widget)
            style.polish(widget)

    def set_error_state(self, widget: QWidget) -> None:
        self.set_state(widget, "error")

    def set_default_state(self, widget: QWidget) -> None:
        self.set_state(widget, "default")

    def set_success_state(self, widget: QWidget) -> None:
        self.set_state(widget, "success")

    @abc.abstractmethod
    def get_val(self, prop: ScrutinyThemeProperties) -> Any:
        pass

    @abc.abstractmethod
    def name(self) -> str:
        pass


_loaded_theme: Optional[ScrutinyTheme] = None


def scrutiny_get_theme() -> ScrutinyTheme:
    global _loaded_theme
    if _loaded_theme is None:
        raise RuntimeError("A theme must be loaded first")
    return _loaded_theme


def scrutiny_get_theme_prop(prop: ScrutinyThemeProperties) -> Any:
    return scrutiny_get_theme().get_val(prop)


def scrutiny_set_theme(app: QApplication, theme: ScrutinyTheme) -> None:
    global _loaded_theme
    _loaded_theme = theme
    theme.apply_to_app(app)
