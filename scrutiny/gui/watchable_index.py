__all__ = ['WatchableIndex', 'WatchableIndexError']


from scrutiny import sdk
from typing import Dict, Iterable, List, Union
from qtpy.QtCore import Signal, QObject
import threading
from dataclasses import dataclass


@dataclass
class ParsedFullyQualifiedName:
    __slots__ = ['watchable_type', 'path']

    watchable_type:sdk.WatchableType
    path:str

class WatchableIndexError(Exception):
    pass

FQN_TYPE_MAP_S2WT = {
    'var' : sdk.WatchableType.Variable,
    'alias' : sdk.WatchableType.Alias,
    'rpv' : sdk.WatchableType.RuntimePublishedValue,
}

FQN_TYPE_MAP_WT2S: Dict[sdk.WatchableType, str] = {v: k for k, v in FQN_TYPE_MAP_S2WT.items()}

class WatchableIndex:
    @dataclass
    class NodeContent:
        watchables:List[sdk.WatchableConfiguration]
        subtree:List[str]

    _content: Dict[sdk.WatchableType, Dict[str, sdk.WatchableConfiguration]]
    _lock:threading.Lock

    def __init__(self) -> None:
        self._content = {
            sdk.WatchableType.Variable : {},
            sdk.WatchableType.Alias : {},
            sdk.WatchableType.RuntimePublishedValue : {}
        }
        self._lock = threading.Lock()
    
    def _get_parts(self, path:str) -> List[str]:
        parts = [x for x in path.split('/') if x]
        return parts

    def _add_watchable(self, path:str, obj:sdk.WatchableConfiguration) -> None:
        parts = self._get_parts(path)
        if len(parts) == 0:
            raise WatchableIndexError(f"Empty path : {path}") 
        node = self._content[obj.watchable_type]
        for i in range(len(parts)-1):
            part = parts[i]
            if part not in node:
                node[part] = {}
            node = node[part]
        if parts[-1] in node:
            raise WatchableIndexError(f"Cannot insert a watchable at location {path}. Another watchable already uses that path.")
        node[parts[-1]] = obj

    def _get_item(self, watchable_type:sdk.WatchableType, path:str) -> Union[NodeContent, sdk.WatchableConfiguration]:
        parts = self._get_parts(path)
        node = self._content[watchable_type]
        for part in parts:
            if part not in node:
                raise WatchableIndexError(f"Inexistent path : {path} ")
            node = node[part]

        if isinstance(node, dict):
            return self.NodeContent(
                watchables=[val for val in node.values() if isinstance(val, sdk.WatchableConfiguration)],
                subtree=[name for name, val in node.items() if isinstance(val, dict)]
            )
        elif isinstance(node, sdk.WatchableConfiguration):
            return node
        else:
            raise WatchableIndexError(f"Unexpected item of type {node.__class__.__name__} inside the index")
    
    @classmethod
    def _validate_fqn(cls, fqn:ParsedFullyQualifiedName, desc:sdk.WatchableConfiguration) -> None:
        if fqn.watchable_type!= desc.watchable_type:
            raise WatchableIndexError("Watchable fully qualified name doesn't embded the type correctly.")
        
    def _get(self, wt:sdk.WatchableType, path:str) -> sdk.WatchableConfiguration:
        try:
            return self._content[wt][path]
        except KeyError as e:
            raise KeyError(f"No watcahble located at {path}") from e
    
    def _has_data(self, watchable_type:sdk.WatchableType) -> bool:
        return len(self._content[watchable_type]) > 0

    @staticmethod
    def parse_fqn(fqn:str) -> ParsedFullyQualifiedName:
        """Parses a fully qualified name and return the information needed to query the index.
        
        :param fqn: The fully qualified name
        
        :return: An object containing the type and the tree path separated
        """
        index = fqn.find(':')
        if index == -1:
            raise WatchableIndexError("Bad fully qualified name")
        typestr = fqn[0:index]
        if typestr not in FQN_TYPE_MAP_S2WT:
            raise WatchableIndexError(f"Unknown watchable type {typestr}")
    
        return ParsedFullyQualifiedName(
            watchable_type=FQN_TYPE_MAP_S2WT[typestr],
            path=fqn[index+1:]
        )

    @staticmethod
    def make_fqn(watchable_type:sdk.WatchableType, path:str) -> str:
        """Create a string representation that conveys enough information to find a specific element in the index.
        Contains the type and the tree path. 
        
        :param watchable_type: The SDK watchable type
        :param path: The tree path
        
        :return: A fully qualified name containing the type and the tree path
        """
        return f"{FQN_TYPE_MAP_WT2S[watchable_type]}:{path}"

    def read(self, watchable_type:sdk.WatchableType, path:str) -> Union[NodeContent, sdk.WatchableConfiguration]:
        """Read a node inside the index.
        
        :watchable_type: The type of node to read
        :path: The tree path of the node

        :return: The node content. Either a watchable or a description of the subnodes
        """
        with self._lock:
            return self._get_item(watchable_type, path)

    def add_watchable(self, path:str, obj:sdk.WatchableConfiguration) -> None:
        """Adds a watcahble inside the index

        :param path: The tree path of the node
        :param obj: The watchable configuration object
        """

        with self._lock:
            return self._add_watchable(path, obj)
    
    def add_watchable_fqn(self, fqn:str, obj:sdk.WatchableConfiguration) -> None:
        """Adds a watcahble inside the index using a fully qualified name

        :param fqn: The fully qualified name created using ``make_fqn()``
        :param obj: The watchable configuration object
        """
        parsed = self.parse_fqn(fqn)
        self._validate_fqn(parsed, obj)
        return self.add_watchable(parsed.path, obj)
    
    def read_fqn(self, fqn:str) -> Union[NodeContent, sdk.WatchableConfiguration]:
        """Read a node inside the index using a fully qualified name.
        
        :param fqn: The fully qualified name created using ``make_fqn()``

        :return: The node content. Either a watchable or a description of the subnodes
        """        
        parsed = self.parse_fqn(fqn)
        node = self.read(parsed.watchable_type, parsed.path)

        return node

    def add_content(self, data:Dict[sdk.WatchableType, Dict[str, sdk.WatchableConfiguration]]) -> None:
        """Add content of the given types.
        Triggers ``changed``.  May trigger ``filled`` if all types have data after calling this function.
        
        :param data: The data to add. Classified in dict[watchable_type][path]. 
        """
        with self._lock:
            for subdata in data.values():
                for path, wc in subdata.items():
                    self._add_watchable(path, wc)
    
    def clear_content_by_types(self, watchable_types:Iterable[sdk.WatchableType]) -> bool:
        """
        Clear the content of the given type from the index. 
        May triggers ``changed`` and ``cleared`` if data was actually removed.

        :return: ``True`` if data was removed. ``False`` if the nothing was removed (already empty)
        """
        with self._lock:
            changed = False
            for watchable_type in watchable_types:
                had_data = len(self._content[watchable_type]) > 0
                self._content[watchable_type] = {}

                if had_data:
                    changed = True
            
            return changed

    def clear(self) -> bool:
        """
        Clear all the content from the index.

        :return: ``True`` if data was removed. ``False`` if the nothing was removed (already empty) 
        """
        with self._lock:
            had_data = False
            for wt in [sdk.WatchableType.Variable, sdk.WatchableType.Alias, sdk.WatchableType.RuntimePublishedValue]:
                if self._has_data(wt):
                    had_data = True

            self._content[sdk.WatchableType.Variable] = {}
            self._content[sdk.WatchableType.Alias] = {}
            self._content[sdk.WatchableType.RuntimePublishedValue] = {}
        
        return had_data

    def has_data(self, watchable_type:sdk.WatchableType) -> bool:
        """Tells if there is data of the given type inside the index
        
        :param watchable_type: The type of watchable to look for
        :return: ``True`` if there is data of that type. ``False otherwise``
        """
        with self._lock:
            return self._has_data(watchable_type)
