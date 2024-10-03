__all__ = ['QtAds']

# Entry point to load QTAdvancewdDockingSystem using either PyQt or PySide
# https://github.com/mborgerson/Qt-Advanced-Docking-System

available = True
try: 
    from PyQtAds import ads as QtAds
except ImportError:
    try:
        import PySide6QtAds as QtAds
    except ImportError:
        available = False

if not available:
    raise ImportError("QT Advanced Docking System is not available. You need either PyQtAds or PySide6QtAds installed.")