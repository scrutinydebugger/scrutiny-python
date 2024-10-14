#    qtads.py
#        Loads QT Advanced Docking System using either PySide or PyQT
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['QtAds']

# Entry point to load QTAdvancewdDockingSystem using either PyQt or PySide
# https://github.com/mborgerson/Qt-Advanced-Docking-System

available = True
try: 
    from PyQtAds import ads as QtAds    # type: ignore
except ImportError:
    try:
        import PySide6QtAds as QtAds    # type: ignore
    except ImportError:
        available = False

if not available:
    raise ImportError("QT Advanced Docking System is not available. You need either PyQtAds or PySide6QtAds installed.")
