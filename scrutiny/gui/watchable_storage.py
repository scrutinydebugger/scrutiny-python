from scrutiny import sdk
from typing import Dict, Iterable
from qtpy.QtCore import Signal, QObject
import threading

class WatchableStorage:
    _content: Dict[sdk.WatchableType, Dict[str, sdk.WatchableConfiguration]]
    _lock:threading.Lock

    class _Signals(QObject):    # QObject required for signals to work
        """Signals offered to the outside worl"""
        filled = Signal()
        cleared = Signal()
        changed = Signal()


    def __init__(self) -> None:
        self._content = {
            sdk.WatchableType.Variable : {},
            sdk.WatchableType.Alias : {},
            sdk.WatchableType.RuntimePublishedValue : {}
        }
        self._lock = threading.Lock()

        self.signals = self._Signals()
    
    def set_content_by_types(self, watchable_types:Iterable[sdk.WatchableType], data:Dict[sdk.WatchableType, Dict[str, sdk.WatchableConfiguration]], copy:bool=False) -> None:
        with self._lock:
            for watchable_type in watchable_types:
                if copy:
                    self._content[watchable_type] = data[watchable_type].copy()
                else:
                    self._content[watchable_type] = data[watchable_type]

            self.signals.changed.emit()

            filled = True
            for wt in [sdk.WatchableType.Variable, sdk.WatchableType.Alias, sdk.WatchableType.RuntimePublishedValue]:
                if not self._has_data(wt):
                    filled = False
            
            if filled:
                self.signals.filled.emit()
    
    def clear_content_by_types(self, watchable_types:Iterable[sdk.WatchableType]) -> None:
        with self._lock:
            changed = False
            for watchable_type in watchable_types:
                had_data = len(self._content[watchable_type]) > 0
                self._content[watchable_type] = {}

                if had_data:
                    changed = True
            
            if changed:
                self.signals.emit()
            
            is_cleared = True
            for wt in [sdk.WatchableType.Variable, sdk.WatchableType.Alias, sdk.WatchableType.RuntimePublishedValue]:
                if len(self._content[wt]) > 0:
                    is_cleared = False
            
            if is_cleared and changed:
                self.signals.cleared.emit()

    def clear(self) -> None:
        with self._lock:
            had_data = False
            for wt in [sdk.WatchableType.Variable, sdk.WatchableType.Alias, sdk.WatchableType.RuntimePublishedValue]:
                if self._has_data(wt):
                    had_data = True

            self._content[sdk.WatchableType.Variable] = {}
            self._content[sdk.WatchableType.Alias] = {}
            self._content[sdk.WatchableType.RuntimePublishedValue] = {}

            if had_data:
                self.signals.cleared.emit()
                self.signals.changed.emit()



    def _has_data(self, watchable_type:sdk.WatchableType) -> bool:
        return len(self._content[watchable_type]) > 0

    def has_data(self, watchable_type:sdk.WatchableType) -> bool:
        with self._lock:
            return self._has_data(watchable_type)
