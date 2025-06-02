#    shiboken_ref_keeper.py
#        A simple tool that keeps a reference of a QT object until the internal C++ object
#        is deleted.
#        Required to pass local python objects to modules that does not take ownership of
#        the object
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['ShibokenRefKeeper']

from PySide6.QtCore import QObject
import shiboken6
from scrutiny.tools.typing import *


class ShibokenRefKeeper:
    """Tool to keep a python object alive by keeping a reference to it. 
    Can be used for some Qt or QtAds functions where a local object is created and ownership is not transfered to QT.
    In that case we need to keep the object alive somewhere until it is not needed anymore.
    """

    _storage: Dict[int, QObject]

    def __init__(self) -> None:
        self._storage = {}

    def insert(self, o: QObject) -> None:
        self._storage[id(o)] = o

    def prune(self) -> None:
        """Remove all objects where the internal C++ object has been deleted"""
        for k in list(self._storage.keys()):
            o = self._storage[k]
            if not shiboken6.isValid(o):
                del self._storage[k]
