#    watchable_registry.py
#        A storage object that keeps a local copy of all the watchable (Variable/Alias/RPV)
#        avaialble on the server.
#        Lots of overlapping feature with the server datastore, with few fundamentals differences.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = [
    'WatchableRegistry', 
    'WatchableRegistryError', 
    'WatchableRegistryNodeContent',
    'WatchableValue',
    'WatcherValueUpdateCallback',
    'GlobalWatchCallback',
    'GlobalUnwatchCallback'
    ]


from scrutiny import sdk
from typing import Dict, List, Union, Optional, Callable, Set, Any, Tuple
import threading
from dataclasses import dataclass
import logging


@dataclass
class ParsedFullyQualifiedName:
    __slots__ = ['watchable_type', 'path']

    watchable_type:sdk.WatchableType
    path:str

class WatchableRegistryError(Exception):
    pass

TYPESTR_MAP_S2WT = {
    'var' : sdk.WatchableType.Variable,
    'alias' : sdk.WatchableType.Alias,
    'rpv' : sdk.WatchableType.RuntimePublishedValue,
}

TYPESTR_MAP_WT2S: Dict[sdk.WatchableType, str] = {v: k for k, v in TYPESTR_MAP_S2WT.items()}

WatchableValue = Union[int, float, bool]
WatcherValueUpdateCallback = Callable[[str, sdk.WatchableConfiguration, WatchableValue], None]
GlobalWatchCallback = Callable[[str, str, sdk.WatchableConfiguration], None]
GlobalUnwatchCallback = Callable[[str, str, sdk.WatchableConfiguration], None]

@dataclass(init=False)
class WatchableRegistryEntryNode:
    """Leaf node in the tree. This object is internal and never given to the user."""
    configuration:sdk.WatchableConfiguration
    value:Optional[WatchableValue]
    watchers:Dict[str, WatcherValueUpdateCallback]
    display_path:str

    def __init__(self, display_path:str, config:sdk.WatchableConfiguration) -> None:
        self.display_path = display_path
        self.configuration = config
        self.value=None
        self.watchers={}

    def register_value_update_callback(self, watcher_id:str, callback:WatcherValueUpdateCallback) -> None:
        if watcher_id in self.watchers:
            raise WatchableRegistryError(f"A callback on {self.configuration.watchable_type.name}:{self.display_path} has already been registered to watcher {watcher_id}")
        
        if not callable(callback):
            raise ValueError("Callback is not a callable")
        
        self.watchers[watcher_id] = callback
    
    def unregister_value_update_callback(self, watcher_id:str) -> None:
        if watcher_id not in self.watchers:
            raise WatchableRegistryError(f"No callback has been registered to watcher {watcher_id}")
        
        del self.watchers[watcher_id]
    
    def watcher_count(self) -> int:
        return len(self.watchers)
    
    def has_callback_registered(self, watcher_id:str) -> bool:
        return watcher_id in self.watchers

    def update_value(self, value:WatchableValue) -> None:
        self.value = value
        for watcher_id, callback in self.watchers.items():
            callback(watcher_id, self.configuration, value)

    def get_value(self) -> Optional[WatchableValue]:
        return self.value

@dataclass(frozen=True)
class WatchableRegistryNodeContent:
    """Node in the tree. This can be given to the user."""
    __slots__ = ['watchables', 'subtree']
    watchables:Dict[str, sdk.WatchableConfiguration]
    subtree:List[str]

class WatchableRegistry:
    """Contains a copy of the watchable list available on the server side
    Act as a relay to dispatch value update event to the internal widgets"""
    _trees:  Dict[sdk.WatchableType, Any]
    _lock:threading.Lock
    _watched_entries:Dict[str, WatchableRegistryEntryNode] 
    _global_watch_callbacks:Optional[GlobalWatchCallback]
    _global_unwatch_callbacks:Optional[GlobalUnwatchCallback]
    _logger:logging.Logger
    _tree_change_counters: Dict[sdk.WatchableType, int]
    
    def __init__(self) -> None:
        self._trees = {
            sdk.WatchableType.Variable : {},
            sdk.WatchableType.Alias : {},
            sdk.WatchableType.RuntimePublishedValue : {}
        }
        self._tree_change_counters = {
            sdk.WatchableType.Variable : 0,
            sdk.WatchableType.Alias : 0,
            sdk.WatchableType.RuntimePublishedValue : 0
        }

        self._lock = threading.Lock()
        self._watched_entries = {}
        self._global_watch_callbacks = None
        self._global_unwatch_callbacks = None
        self._logger = logging.getLogger(self.__class__.__name__)
    
    @staticmethod
    def split_path(path:str) -> List[str]:
        """Split a tree path in parts"""
        return [x for x in path.split('/') if x]
    
    @staticmethod
    def join_path(pieces:List[str]) -> str:
        """Merge tree path together"""
        return '/'.join([x for x in pieces if x])

    def _add_watchable_no_lock(self, path:str, config:sdk.WatchableConfiguration) -> None:
        """Adds a single watchable to the tree storage without using a lock"""
        parts = self.split_path(path)
        if len(parts) == 0:
            raise WatchableRegistryError(f"Empty path : {path}") 
        node = self._trees[config.watchable_type]
        for i in range(len(parts)-1):
            part = parts[i]
            if part not in node:
                node[part] = {}
            node = node[part]
        if parts[-1] in node:
            raise WatchableRegistryError(f"Cannot insert a watchable at location {path}. Another watchable already uses that path.")
        node[parts[-1]] = WatchableRegistryEntryNode(
            display_path=path,  # Required for proper error messages.
            config=config
            )

    def _get_node_with_lock(self, watchable_type:sdk.WatchableType, path:str) -> Union[WatchableRegistryNodeContent, WatchableRegistryEntryNode]:
        """Read a node in the tree and locks the tree while doing it."""
        with self._lock:
            parts = self.split_path(path)
            node = self._trees[watchable_type]
            for part in parts:
                if part not in node:
                    raise WatchableRegistryError(f"Inexistent path : {path} ")
                node = node[part]

            if isinstance(node, dict):
                return WatchableRegistryNodeContent(
                    watchables=dict( (name, val.configuration) for name, val in node.items() if isinstance(val, WatchableRegistryEntryNode)),
                    subtree=[name for name, val in node.items() if isinstance(val, dict)]
                )
            elif isinstance(node, WatchableRegistryEntryNode):
                return node
            else:
                raise WatchableRegistryError(f"Unexpected item of type {node.__class__.__name__} inside the registry")
    
    def _has_data(self, watchable_type:sdk.WatchableType) -> bool:
        """Tells if the tree attached to a given watchable type contains data"""
        return len(self._trees[watchable_type]) > 0

    def update_value_fqn(self, fqn:str, value:WatchableValue) -> None:
        """Update the watchable value and inform all watchers
        
        :param fqn: The watchable fully qualified name
        :param value: The value to broadcast
        """
        parsed = self.parse_fqn(fqn)
        self.update_value(parsed.watchable_type, parsed.path, value)

    def update_watched_entry_value_by_server_id(self, server_id:str, value:WatchableValue) -> None:
        """Update the watchable value and inform all watchers only if part of the watched entries
        
        :param server_id: The server ID received by the server
        :param value: The value to broadcast
        
        """
        try:
            entry = self._watched_entries[server_id]
        except KeyError:
            return  # Silently ignore
        
        entry.update_value(value)

    def update_value(self, watchable_type:sdk.WatchableType, path:str, value:WatchableValue) -> None:
        """Update the watchable value and inform all watchers
        
        :param watchable_type: The watchable type
        :param path: The watchable tree path
        :param value: The value to broadcast
        """
        node = self._get_node_with_lock(watchable_type, path)
        if not isinstance(node, WatchableRegistryEntryNode):
            raise WatchableRegistryError("Cannot update a value on something that is not a Watchable")
        node.update_value(value)
    
    def watch_fqn(self, watcher_id:str, fqn:str, callback:WatcherValueUpdateCallback) -> None:
        """Adds a watcher on the given watchable and register a callback to be 
        invoked when its value is updated 
        
        :param watcher_id: A string that identifies the owner of the callback. Passed back when the callback is invoked
        :param fqn: The watchable fully qualified name
        :param callback: The callback
        """
        parsed = self.parse_fqn(fqn)
        self.watch(watcher_id, parsed.watchable_type, parsed.path, callback)

    def watch(self, watcher_id:str, watchable_type:sdk.WatchableType, path:str, callback:WatcherValueUpdateCallback) -> None:
        """Adds a watcher on the given watchable and register a callback to be 
        invoked when its value is updated 
        
        :param watcher_id: A string that identifies the owner of the callback. Passed back when the callback is invoked
        :param watchable_type: The watchable type
        :param path: The watchable tree path
        :param callback: The callback
        """
        node = self._get_node_with_lock(watchable_type, path)
        if not isinstance(node, WatchableRegistryEntryNode):
            raise WatchableRegistryError("Cannot watch something that is not a Watchable")
        
        node.register_value_update_callback(watcher_id, callback)
        
        with self._lock:
            self._watched_entries[node.configuration.server_id] = node
        
        if self._global_watch_callbacks is not None:
            self._global_watch_callbacks(watcher_id, node.display_path, node.configuration)

    def unwatch(self, watcher_id:str, watchable_type:sdk.WatchableType, path:str) -> None:
        """Remove a the given watcher from the watcher list of the given node.
        
        :param watcher_id: A string that identifies the owner of the callback. Passed back when the callback is invoked
        :param watchable_type: The watchable type
        :param path: The watchable tree path
        """
        node = self._get_node_with_lock(watchable_type, path)
        if not isinstance(node, WatchableRegistryEntryNode):
            raise WatchableRegistryError("Cannot unwatch something that is not a Watchable")
        
        if node.has_callback_registered(watcher_id):
            node.unregister_value_update_callback(watcher_id)
        
        if node.watcher_count() == 0:
            try:
                del self._watched_entries[node.configuration.server_id]
            except KeyError:
                pass
        
        if self._global_unwatch_callbacks is not None:
            self._global_unwatch_callbacks(watcher_id, node.display_path, node.configuration)
    
    def unwatch_fqn(self, watcher_id:str, fqn:str) -> None:
        """Remove a the given watcher from the watcher list of the given node.
        
        :param watcher_id: A string that identifies the owner of the callback. Passed back when the callback is invoked
        :param watchable_type: The watchable type
        :param path: The watchable tree path
        """
        parsed = self.parse_fqn(fqn)
        self.unwatch(watcher_id, parsed.watchable_type, parsed.path)

    def watcher_count_by_server_id(self, server_id:str) -> int:
        """Return the number of watcher on a node, identified by its server_id
        
        :param server_id: The watchable server_id
        :return: The number of watchers 
        """
        try:
            entry = self._watched_entries[server_id]
        except KeyError:
            return 0
        return entry.watcher_count()

    def watcher_count_fqn(self, fqn:str) -> int:
        """Return the number of watcher on a node
        
        :param fqn: The watchable fully qualified name
        :return: The number of watchers
        """
        parsed = self.parse_fqn(fqn)
        return self.watcher_count(parsed.watchable_type, parsed.path)
       
    def watcher_count(self, watchable_type:sdk.WatchableType, path:str) -> int:
        """Return the number of watcher on a node
        
        :param watchable_type: The watchable type
        :param path: The watchable tree path
        :return: The number of watchers
        """
        node = self._get_node_with_lock(watchable_type, path)
        if not isinstance(node, WatchableRegistryEntryNode):
            raise WatchableRegistryError("Cannot get the watcher count of something that is not a Watchable")
        return node.watcher_count()
    
    def watched_entries_count(self) -> int:
        """Return the total number of watchable being watched"""
        return len(self._watched_entries)
    
    def get_value_fqn(self, fqn:str) -> Optional[WatchableValue]:
        """Reads the last value written to this watchable
        
        :param fqn: The watchable fully qualified name
        :return: The last value written or ``None``
        """
        parsed = self.parse_fqn(fqn)
        return self.get_value(parsed.watchable_type, parsed.path)

    def get_value(self, watchable_type:sdk.WatchableType, path:str) -> Optional[WatchableValue]:
        """Reads the last value written to this watchable
        
        :param watchable_type: The watchable type
        :param path: The watchable tree path
        :return: The last value written or ``None``
        """
        node = self._get_node_with_lock(watchable_type, path)
        if not isinstance(node, WatchableRegistryEntryNode):
            raise WatchableRegistryError("Cannot read a value on something that is not a Watchable")
        return node.get_value()

    def read(self, watchable_type:sdk.WatchableType, path:str) -> Union[WatchableRegistryNodeContent, sdk.WatchableConfiguration]:
        """Read a node inside the registry.
        
        :watchable_type: The type of node to read
        :path: The tree path of the node

        :return: The node content. Either a watchable or a description of the subnodes
        """
        node = self._get_node_with_lock(watchable_type, path)
        if isinstance(node, WatchableRegistryEntryNode):
            return node.configuration
        return node

    def add_watchable(self, path:str, obj:sdk.WatchableConfiguration) -> None:
        """Adds a watchable inside the registry

        :param path: The tree path of the node
        :param obj: The watchable configuration object
        """
        with self._lock:
            return self._add_watchable_no_lock(path, obj)
    
    def add_watchable_fqn(self, fqn:str, obj:sdk.WatchableConfiguration) -> None:
        """Adds a watchable inside the registry using a fully qualified name

        :param fqn: The fully qualified name created using ``make_fqn()``
        :param obj: The watchable configuration object
        """
        parsed = self.parse_fqn(fqn)
        self._validate_fqn(parsed, obj)
        return self.add_watchable(parsed.path, obj)
    
    def read_fqn(self, fqn:str) -> Union[WatchableRegistryNodeContent, sdk.WatchableConfiguration]:
        """Read a node inside the registry using a fully qualified name.
        
        :param fqn: The fully qualified name created using ``make_fqn()``

        :return: The node content. Either a watchable or a description of the subnodes
        """        
        parsed = self.parse_fqn(fqn)
        return self.read(parsed.watchable_type, parsed.path)

    def add_content(self, data:Dict[sdk.WatchableType, Dict[str, sdk.WatchableConfiguration]]) -> None:
        """Add content of the given types.
        Triggers ``changed``.  May trigger ``filled`` if all types have data after calling this function.
        
        :param data: The data to add. Classified in dict[watchable_type][path]. 
        """
        touched = {
            sdk.WatchableType.Variable : False,
            sdk.WatchableType.Alias : False,
            sdk.WatchableType.RuntimePublishedValue : False,
        }
        with self._lock:
            for subdata in data.values():
                for path, wc in subdata.items():
                    touched[wc.watchable_type] = True
                    self._add_watchable_no_lock(path, wc)
            
            for wt in touched:
                if touched[wt]:
                    self._tree_change_counters[wt] += 1
    
    def clear_content_by_type(self, watchable_type:sdk.WatchableType) -> bool:
        """
        Clear the content of the given type from the registry. 
        May triggers ``changed`` and ``cleared`` if data was actually removed.

        :return: ``True`` if data was removed. ``False`` if the nothing was removed (already empty)
        """
        with self._lock:
            changed = False
            had_data = len(self._trees[watchable_type]) > 0
            self._trees[watchable_type] = {}

            if had_data:
                changed = True
                self._tree_change_counters[watchable_type] += 1

            to_remove:Set[str] = set()
            for server_id, entry in self._watched_entries.items():
                if entry.configuration.watchable_type == watchable_type:
                    entry.watchers.clear()
                    to_remove.add(server_id)
            
            for server_id in to_remove:
                del self._watched_entries[server_id]

        return changed

    def clear(self) -> bool:
        """
        Clear all the content from the registry.

        :return: ``True`` if data was removed. ``False`` if the nothing was removed (already empty) 
        """
        with self._lock:
            self._watched_entries.clear()
            had_data = False
            for wt in [sdk.WatchableType.Variable, sdk.WatchableType.Alias, sdk.WatchableType.RuntimePublishedValue]:
                if self._has_data(wt):
                    had_data = True
                    self._tree_change_counters[wt] += 1

            self._trees[sdk.WatchableType.Variable] = {}
            self._trees[sdk.WatchableType.Alias] = {}
            self._trees[sdk.WatchableType.RuntimePublishedValue] = {}
        
        return had_data

    def has_data(self, watchable_type:sdk.WatchableType) -> bool:
        """Tells if there is data of the given type inside the registry
        
        :param watchable_type: The type of watchable to look for
        :return: ``True`` if there is data of that type. ``False otherwise``
        """
        with self._lock:
            return self._has_data(watchable_type)


    def register_global_watch_callback(self, watch_callback:GlobalWatchCallback, unwatch_callback:GlobalUnwatchCallback ) -> None:
        """Register a callback to be called whenever a new watcher is being added or removed on an entry
        
        :param watch_callback: Callback invoked on ``watch`` invocation
        :param unwatch_callback: Callback invoked on ``unwatch`` invocation
        """
        self._global_watch_callbacks = watch_callback
        self._global_unwatch_callbacks = unwatch_callback
    

    def get_change_counters(self) -> Dict[sdk.WatchableType, int]:
        return self._tree_change_counters.copy()

    @classmethod
    def _validate_fqn(cls, fqn:ParsedFullyQualifiedName, desc:sdk.WatchableConfiguration) -> None:
        if fqn.watchable_type!= desc.watchable_type:
            raise WatchableRegistryError("Watchable fully qualified name doesn't embded the type correctly.")
  
    @staticmethod
    def parse_fqn(fqn:str) -> ParsedFullyQualifiedName:
        """Parses a fully qualified name and return the information needed to query the registry.
        
        :param fqn: The fully qualified name
        
        :return: An object containing the type and the tree path separated
        """
        colon_position = fqn.find(':')
        if colon_position == -1:
            raise WatchableRegistryError("Bad fully qualified name")
        typestr = fqn[0:colon_position]
        if typestr not in TYPESTR_MAP_S2WT:
            raise WatchableRegistryError(f"Unknown watchable type {typestr}")
    
        return ParsedFullyQualifiedName(
            watchable_type=TYPESTR_MAP_S2WT[typestr],
            path=fqn[colon_position+1:]
        )

    @staticmethod
    def make_fqn(watchable_type:sdk.WatchableType, path:str) -> str:
        """Create a string representation that conveys enough information to find a specific element in the registry.
        Contains the type and the tree path. 
        
        :param watchable_type: The SDK watchable type
        :param path: The tree path
        
        :return: A fully qualified name containing the type and the tree path
        """
        return f"{TYPESTR_MAP_WT2S[watchable_type]}:{path}"
    
    @staticmethod
    def extend_fqn(fqn:str, pieces:Union[str, List[str]]) -> str:
        """Add one or many path parts to an existing Fully Qualified Name
        Ex. var:/a/b/c + ['x', 'y'] = var:/a/b/c/x/y
        
        :param fqn: The Fully Qualified Name to extend
        :param pieces: The parts to add
        """
        if isinstance(pieces, str):
            pieces = [pieces]
        parsed = WatchableRegistry.parse_fqn(fqn)
        path_parts = WatchableRegistry.split_path(parsed.path)
        prefix = ''
        if len(path_parts) > 0:
            index = parsed.path.find(path_parts[0])
            if index >= 0:
                prefix = parsed.path[0:index]
        return WatchableRegistry.make_fqn(parsed.watchable_type, prefix+WatchableRegistry.join_path(path_parts + pieces) )

    @staticmethod
    def fqn_equal(fqn1:str, fqn2:str) -> bool:
        parsed1 = WatchableRegistry.parse_fqn(fqn1)
        parsed2 = WatchableRegistry.parse_fqn(fqn2)

        if parsed1.watchable_type != parsed2.watchable_type:
            return False
        
        path1 = WatchableRegistry.split_path(parsed1.path)
        path2 = WatchableRegistry.split_path(parsed2.path)

        if len(path1) != len(path2):
            return False
        for i in range(len(path1)):
            if path1[i] != path2[i]:
                return False

        return True
