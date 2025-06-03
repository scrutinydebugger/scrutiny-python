#    opengl.py
#        OpenGL related stuff
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['prepare_for_opengl']

from PySide6.QtWidgets import QWidget


def prepare_for_opengl(widget: QWidget) -> None:
    # QTBUG-108190. PySide6.4 regression. Workaround to force OpenGL to initialize
    from PySide6.QtOpenGLWidgets import QOpenGLWidget
    dummy_widget = QOpenGLWidget(widget)
    dummy_widget.setVisible(False)
