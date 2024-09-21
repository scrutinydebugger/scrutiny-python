__all__ = ['Sidebar']


from PySide6.QtCore import QEvent
from qtpy.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from qtpy.QtCore import Qt, QSize, QMimeData
from qtpy.QtGui import QDragMoveEvent, QDragEnterEvent, QDragLeaveEvent, QDrag, QFontMetrics
from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from scrutiny.gui.exceptions import GuiError

from typing import List, Type, Dict, Optional

SIDEBAR_ELEMENT_W = 64
SIDEBAR_W = SIDEBAR_ELEMENT_W + 12
SIDEBAR_ELEMENT_ICON_H = 48

class SideBarMultilineLabel(QLabel):
    """Label that goes below an icon in the side bar.
    It implements a cusom word wrapping function for a known parent width.
    Meant to avoid using SetWordWrap that enables richText mode that makes it hard to guess the size for a layout.
    """

    _initial_text:str
    def __init__(self, *args, **qwargs):
        super().__init__(*args, **qwargs)
        self._initial_text = self.text()
        
        # Enabling wordwrap may set the aprent layout in FreeResize mode
        # https://doc.qt.io/qt-5/layout.html#manual-layout
        # minimumSizeHint is required for proper layout
        #self.setWordWrap(True)  
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignCenter)

    
    def compute_word_wrap(self, text:str, w:int) -> str:
        """Computes the word wrapped version of a string"""
        metrics = QFontMetrics(self.font())
        if w <= 0:
            return text
        i=0
        last_space:Optional[int]=None
        lines:List[str] = []
        while len(text) > 0 and i<len(text):
            if text[i] == ' ':
                last_space = i
            if metrics.width(text[0:i]) >=w:
                if last_space is not None and last_space > 0:
                    lines.append(text[0:last_space])
                    text = text[last_space+1:]
                    i=0
                    last_space = None
                else:
                    lines.append(text[0:i])
                    text = text[i:]
                    i=0
            i+=1
        if len(text) > 0:
            lines.append(text)
        outtext = '\n'.join(lines)
        return outtext

    def setText(self, text:str) -> None:
        super().setText(text)
        self._initial_text = text

    def changeEvent(self, arg__1: QEvent) -> None:
        super().setText(self.compute_word_wrap(self._initial_text, self.parentWidget().width()))
        return super().changeEvent(arg__1)



class Sidebar(QWidget):
    _sidebar_elements:Dict[Type[ScrutinyGUIBaseComponent], QWidget]

    def __init__(self, components:List[Type[ScrutinyGUIBaseComponent]]) -> None:
        super().__init__()

        self._sidebar_elements = {}

        self.setMaximumWidth(SIDEBAR_W)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))
        sidebar_layout = QVBoxLayout(self)
        sidebar_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        sidebar_margin = (SIDEBAR_W - SIDEBAR_ELEMENT_W)//2
        sidebar_layout.setContentsMargins(sidebar_margin,20,sidebar_margin,0)
        sidebar_layout.setSpacing(0)
        
        self.timers = []
        for component in components:
            # Visual part
            sidebar_element = QWidget()
            sidebar_element.setProperty('class', 'sidebar_element')
            sidebar_element.setProperty('scrutiny_component_class', component)

            element_layout = QVBoxLayout(sidebar_element)
            element_layout.setSpacing(0)
            element_layout.setContentsMargins(0,5,0,5)
            sidebar_element.setMaximumWidth(SIDEBAR_ELEMENT_W)
            
            icon_label = QLabel()
            icon = component.get_icon()        
            
            icon_label.setFixedHeight(SIDEBAR_ELEMENT_ICON_H)
            icon_label.setPixmap(icon.scaled(QSize(icon_label.width(), icon_label.height()), Qt.AspectRatioMode.KeepAspectRatio))

            text = SideBarMultilineLabel(component.get_name(), sidebar_element)
            
            element_layout.addWidget(icon_label)
            element_layout.addWidget(text)

            sidebar_layout.addWidget(sidebar_element)

            # Functional part
            self._sidebar_elements[component] = sidebar_element
            sidebar_element.dragMoveEvent=self.dragmove
            sidebar_element.dragEnterEvent=self.dragenter
            sidebar_element.dragLeaveEvent=self.dragleave

            drag = QDrag(sidebar_element)
            mime_data = QMimeData()
#            mime_data.setText()
            drag.setMimeData(mime_data)
            
        
    
    def dragmove(self, event:QDragMoveEvent) -> None:
        print(event)

    def dragenter(self, event:QDragEnterEvent) -> None:
        print(event)

    def dragleave(self, event:QDragLeaveEvent) -> None:
        print(event)
