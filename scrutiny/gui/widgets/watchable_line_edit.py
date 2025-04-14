#    watchable_line_edit.py
#        A textbox that can be manually edited or filled with a watchable element by drag&drop
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import enum
from dataclasses import dataclass

from PySide6.QtWidgets import QLineEdit
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QKeyEvent, QAction, QMouseEvent, QIcon, QPaintEvent, QPainter, QColor
from PySide6.QtCore import Qt, QSize, QPoint, QRect

from scrutiny import tools
from scrutiny.tools.typing import *
from scrutiny.gui.core.scrutiny_drag_data import WatchableListDescriptor
from scrutiny.gui.tools import watchabletype_2_icon
from scrutiny.gui import assets
from scrutiny.gui.core.watchable_registry import WatchableRegistry
from scrutiny.sdk import WatchableType
from scrutiny.gui.themes import get_theme_prop, ScrutinyThemeProperties

@dataclass
class WatchableFQNAndName:
    fqn:str
    name:str

class WatchableLineEdit(QLineEdit):

    class Mode(enum.Enum):
        TEXT = enum.auto()
        WATCHABLE = enum.auto()

    CLEAR_ICON_MARGIN = 2
    CLEAR_ZONE_MARGIN = 2

    _mode:Mode
    _watchable_icon_action:Optional[QAction]
    _clear_icon:QIcon
    _clear_being_clicked:bool
    _mouse_over_clear_button:bool
    _text_mode_enabled:bool
    _loaded_watchable:Optional[WatchableFQNAndName]

    @tools.copy_type(QLineEdit.__init__)
    def __init__(self, *args:Any, **kwargs:Any) -> None:
        super().__init__(*args, **kwargs)
        self._mode = self.Mode.TEXT
        self._icon_action = None
        self._clear_icon = assets.load_icon(assets.Icons.RedX, assets.IconFormat.Tiny)
        self._clear_being_clicked = False
        self._mouse_over_clear_button= False
        self._text_mode_enabled = True
        self._loaded_watchable = None
        self.setAcceptDrops(True)
        self._update_cursor()

    
    def set_text_mode_enabled(self, val:bool) -> None:
        self._text_mode_enabled = val
        if self._mode == self.Mode.TEXT:
            readonly = not self._text_mode_enabled
            self.setReadOnly(readonly)
            self._update_cursor()

    def _clear_button_geometry(self) -> Tuple[QRect, QRect]:
        zone_size = QSize(self.height() - 2*self.CLEAR_ZONE_MARGIN, self.height() - 2*self.CLEAR_ZONE_MARGIN)
        zone_topleft = QPoint(self.width() - zone_size.width() - self.CLEAR_ZONE_MARGIN, self.CLEAR_ZONE_MARGIN)
        
        icon_size = QSize(zone_size.width() - 2*self.CLEAR_ICON_MARGIN, zone_size.height() - 2*self.CLEAR_ICON_MARGIN)
        icon_topleft = QPoint(zone_topleft.x() + self.CLEAR_ICON_MARGIN, zone_topleft.y() + self.CLEAR_ICON_MARGIN)
        
        return (QRect(zone_topleft, zone_size), QRect(icon_topleft, icon_size))

    def dragEnterEvent(self, event:QDragEnterEvent) -> None:
        watchables = WatchableListDescriptor.from_mime(event.mimeData())
        if watchables is not None:
            if len(watchables.data) == 1:
                event.accept()
        super().dragEnterEvent(event)

    def dropEvent(self, event:QDropEvent) -> None:
        watchables = WatchableListDescriptor.from_mime(event.mimeData())
        if watchables is not None:
            if len(watchables.data) == 1:
                watchable = watchables.data[0]
                parsed_fqn = WatchableRegistry.FQN.parse(watchable.fqn)
                self.set_watchable_mode(watchable_type=parsed_fqn.watchable_type, path=parsed_fqn.path, name=watchable.text)
        super().dropEvent(event)

    def set_watchable_mode(self, watchable_type:WatchableType, path:str, name:str) -> None:
        watchable_icon = assets.load_tiny_icon(watchabletype_2_icon(watchable_type))
        self._watchable_icon_action = self.addAction(watchable_icon, QLineEdit.ActionPosition.LeadingPosition)
        self.setText(name)
        self.setReadOnly(True)
        self._mode = self.Mode.WATCHABLE

        margins = self.textMargins()
        click_rect, icon_rect = self._clear_button_geometry()
        margins.setRight(margins.right() + click_rect.width())
        self.setTextMargins(margins)
        self._loaded_watchable = WatchableFQNAndName(
            fqn=WatchableRegistry.FQN.make(watchable_type, path), 
            name=name)
        self._update_cursor()
    
    def _update_cursor(self) -> None:
        if self._mode == self.Mode.WATCHABLE:
            if self._mouse_over_clear_button:
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        elif self._mode == self.Mode.TEXT:
            if self._text_mode_enabled:
                self.setCursor(Qt.CursorShape.IBeamCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
    
    def set_text_mode(self) -> None:
        if self._mode == self.Mode.WATCHABLE:
            assert self._watchable_icon_action is not None
            self.removeAction(self._watchable_icon_action)
            self.setText("")
            readonly = not self._text_mode_enabled
            self.setReadOnly(readonly)
            margins = self.textMargins()
            margins.setRight(0)
            self.setTextMargins(margins)
            self._mode = self.Mode.TEXT
            self._mouse_over_clear_button = False
            self._clear_being_clicked = False
            self._loaded_watchable = None
            self._update_cursor()
        

    def keyPressEvent(self, event:QKeyEvent) -> None:
        if self._mode == self.Mode.WATCHABLE:
            if event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace:
                self.set_text_mode()
        super().keyPressEvent(event)

    def paintEvent(self, event:QPaintEvent) -> None:
        super().paintEvent(event)

        if self._mode == self.Mode.WATCHABLE:
            HOVERED_COLOR = get_theme_prop(ScrutinyThemeProperties.WATCHABLE_LINE_EDIT_CLEAR_BTN_HOVER_COLOR)  
            PRESSED_COLOR = get_theme_prop(ScrutinyThemeProperties.WATCHABLE_LINE_EDIT_CLEAR_BTN_PRESSED_COLOR) 

            click_rect, icon_rect = self._clear_button_geometry()
            pixmap = self._clear_icon.pixmap(icon_rect.size())
            painter = QPainter(self)

            background_color:Optional[QColor] = None
            if self.underMouse():
                if self._clear_being_clicked:
                    background_color = PRESSED_COLOR
                elif self._mouse_over_clear_button:
                    background_color = HOVERED_COLOR
            
            if background_color is not None:
                painter.setPen(background_color)
                painter.setBrush(background_color)
                painter.drawRect(click_rect)
            
            icon_topleft = icon_rect.topLeft()
            if self._clear_being_clicked:
                icon_topleft += QPoint(1,1)

            painter.drawPixmap(icon_topleft, pixmap)
    
    def mouseMoveEvent(self, event:QMouseEvent) -> None:
        if self._mode == self.Mode.WATCHABLE:
            click_rect, icon_rect = self._clear_button_geometry()
            self._mouse_over_clear_button = click_rect.contains(event.pos())

        self._update_cursor()
        self.update()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event:QMouseEvent) -> None:
        super().mousePressEvent(event)
        if self._mode == self.Mode.WATCHABLE:
            click_rect, icon_rect = self._clear_button_geometry()
            if click_rect.contains(event.pos()):
                self._clear_being_clicked = True
                self.update()

    def mouseReleaseEvent(self, event:QMouseEvent) -> None:
        super().mouseReleaseEvent(event)
        if self._mode == self.Mode.WATCHABLE and self._clear_being_clicked:
            click_rect, icon_rect = self._clear_button_geometry()
            if click_rect.contains(event.pos()):
                self.set_text_mode()
        
        self._clear_being_clicked = False
        self.update()

    def get_watchable(self) -> Optional[WatchableFQNAndName]:
        return self._loaded_watchable

    def is_text_mode(self) -> bool:
        return self._mode == self.Mode.TEXT
    
    def is_watchable_mode(self) -> bool:
        return self._mode == self.Mode.WATCHABLE
