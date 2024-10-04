from scrutiny import sdk
from typing import Dict, Iterable, List, Union
from qtpy.QtCore import Signal, QObject
import threading
from dataclasses import dataclass

class WatchableIndexError(Exception):
    pass
@dataclass
class NodeContent:
    watchables:List[sdk.WatchableConfiguration]
    subtree:List[str]

class WatchableIndex:
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
    
    def _get_parts(self, path:str) -> List[str]:
        parts = [x for x in path.split('/') if x]
        if len(parts) == 0:
            raise WatchableIndexError(f"Empty path : {path}") 
        return parts

    def _add_item(self, watchable_type:sdk.WatchableType, path:str, config:sdk.WatchableConfiguration) -> None:
        parts = self._get_parts(path)
        node = self._content[watchable_type]
        for i in range(len(parts)-1):
            part = parts[i]
            if part not in node:
                node[part] = {}
            node = node[part]
        node[parts[-1]] = config

    def _get_item(self, watchable_type:sdk.WatchableType, path:str) -> Union[NodeContent, sdk.WatchableConfiguration]:
        parts = self._get_parts(path)
        node = self._content[watchable_type]
        for part in parts:
            if part not in node:
                raise WatchableIndexError(f"Inexistent path : {path} ")
            node = node[part]

        if isinstance(node, dict):
            return NodeContent(
                watchables=[name for name, val in node.items() if isinstance(val, sdk.WatchableConfiguration)],
                subtree=[name for name, val in node.items() if isinstance(val, dict)]
            )
        elif isinstance(node, sdk.WatchableConfiguration):
            return node
        else:
            raise WatchableIndexError(f"Unexpected item of type {node.__class__.__name__} inside the index")

    
    def set_content(self, data:Dict[sdk.WatchableType, Dict[str, sdk.WatchableConfiguration]]) -> None:
        """Set the content of the given types.
        Triggers ``changed``.  May trigger ``filled`` if all types have data after calling this function.
        
        :param data: The data to add. Classified in dict[watchable_type][path]. 
        """
        with self._lock:
            for watchable_type in data.keys():
                subdata = data[watchable_type]
                self._content[watchable_type] = {}
                for path, wc in subdata.items():
                    self._add_item(watchable_type, path, wc)

            self.signals.changed.emit()

            filled = True
            for wt in [sdk.WatchableType.Variable, sdk.WatchableType.Alias, sdk.WatchableType.RuntimePublishedValue]:
                if not self._has_data(wt):
                    filled = False
            
            if filled:
                self.signals.filled.emit()
    
    def clear_content_by_types(self, watchable_types:Iterable[sdk.WatchableType]) -> None:
        """
        Clear the content of the given type from the index. 
        May triggers ``changed`` and ``cleared`` if data was actually removed.
        """
        with self._lock:
            changed = False
            for watchable_type in watchable_types:
                had_data = len(self._content[watchable_type]) > 0
                self._content[watchable_type] = {}

                if had_data:
                    changed = True
            
            if changed:
                self.signals.changed.emit()
            
            is_cleared = True
            for wt in [sdk.WatchableType.Variable, sdk.WatchableType.Alias, sdk.WatchableType.RuntimePublishedValue]:
                if len(self._content[wt]) > 0:
                    is_cleared = False
            
            if is_cleared and changed:
                self.signals.cleared.emit()

    def clear(self) -> None:
        """
        Clear all the content from the index. Triggers ``changed`` and ``cleared`` 
        """
        with self._lock:
            had_data = False
            for wt in [sdk.WatchableType.Variable, sdk.WatchableType.Alias, sdk.WatchableType.RuntimePublishedValue]:
                if self._has_data(wt):
                    had_data = True

            self._content[sdk.WatchableType.Variable] = {}
            self._content[sdk.WatchableType.Alias] = {}
            self._content[sdk.WatchableType.RuntimePublishedValue] = {}

            if had_data:
                self.signals.changed.emit()
                self.signals.cleared.emit()

    def _get(self, wt:sdk.WatchableType, path:str) -> sdk.WatchableConfiguration:
        try:
            return self._content[wt][path]
        except KeyError as e:
            raise KeyError(f"No watcahble located at {path}") from e
    
    def list_content(self, wt:sdk.WatchableType, path:str) -> NodeContent:
        pass

    def _has_data(self, watchable_type:sdk.WatchableType) -> bool:
        return len(self._content[watchable_type]) > 0

    def has_data(self, watchable_type:sdk.WatchableType) -> bool:
        """Tells if there is data of the given type inside the index
        
        :param watchable_type: The type of watchable to look for
        :return: ``True`` if there is data of that type. ``False otherwise``
        """
        with self._lock:
            return self._has_data(watchable_type)
