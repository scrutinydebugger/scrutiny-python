#    watchable_registry.py
#        A storage object that keeps a local copy of all the watchable (Variable/Alias/RPV)
#        avaialble on the server.
#        Lots of overlapping feature with the server datastore, with few fundamentals differences.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

__all__ = [
    'WatchableRegistry',
    'WatchableRegistryError',
    'WatchableRegistryNodeNotFoundError',
    'WatchableRegistryNodeContent',
    'WatchableValue',
    'WatcherValueUpdateCallback',
    'GlobalWatchCallback',
    'GlobalUnwatchCallback',
    'ValueUpdate'
]


from dataclasses import dataclass
import logging

from scrutiny import sdk
from scrutiny.sdk.listeners import ValueUpdate
from scrutiny.gui.core.threads import QT_THREAD_NAME
from scrutiny import tools
from scrutiny.tools.thread_enforcer import enforce_thread
from scrutiny.tools.typing import *

WatcherIdType = Union[str, int]


@dataclass
class ParsedFullyQualifiedName:
    __slots__ = ['watchable_type', 'path']

    watchable_type: sdk.WatchableType
    path: str


class WatchableRegistryError(Exception):
    pass


class WatchableRegistryNodeNotFoundError(WatchableRegistryError):
    pass


class WatcherNotFoundError(Exception):
    pass


TYPESTR_MAP_S2WT = {
    'var': sdk.WatchableType.Variable,
    'alias': sdk.WatchableType.Alias,
    'rpv': sdk.WatchableType.RuntimePublishedValue,
}

TYPESTR_MAP_WT2S: Dict[sdk.WatchableType, str] = {v: k for k, v in TYPESTR_MAP_S2WT.items()}


WatcherValueUpdateCallback = Callable[[WatcherIdType, List[ValueUpdate]], None]
UnwatchCallback = Callable[[WatcherIdType, str, sdk.WatchableConfiguration], None]
GlobalWatchCallback = Callable[[WatcherIdType, str, sdk.WatchableConfiguration], None]
GlobalUnwatchCallback = Callable[[WatcherIdType, str, sdk.WatchableConfiguration], None]


@dataclass(init=False)
class WatchableRegistryEntryNode:
    """Leaf node in the tree. This object is internal and never given to the user."""
    configuration: sdk.WatchableConfiguration
    server_path: str
    watcher_count: int

    def __init__(self, server_path: str, config: sdk.WatchableConfiguration) -> None:
        self.server_path = server_path
        self.configuration = config
        self.watcher_count = 0


@dataclass(frozen=True)
class WatchableRegistryNodeContent:
    """Node in the tree. This can be given to the user."""
    __slots__ = ['watchables', 'subtree']
    watchables: Dict[str, sdk.WatchableConfiguration]
    subtree: List[str]


@dataclass(init=False)
class Watcher:
    watcher_id: WatcherIdType
    value_update_callback: WatcherValueUpdateCallback
    unwatch_callback: UnwatchCallback
    subscribed_server_id: Set[str]

    def __init__(self,
                 watcher_id: WatcherIdType,
                 value_update_callback: WatcherValueUpdateCallback,
                 unwatch_callback: UnwatchCallback
                 ) -> None:
        if not isinstance(watcher_id, (str, int)):
            raise ValueError("watcher_id is not a string or an int")
        if not callable(value_update_callback):
            raise ValueError("value_update_callback is not a function")
        if not callable(unwatch_callback):
            raise ValueError("unwatch_callback is not a function")

        self.watcher_id = watcher_id
        self.value_update_callback = value_update_callback
        self.unwatch_callback = unwatch_callback
        self.subscribed_server_id = set()


class WatchableRegistry:
    """Contains a copy of the watchable list available on the server side
    Act as a relay to dispatch value update event to the internal widgets"""

    @dataclass(frozen=True)
    class Statistics:
        """(Immutable struct) Internal metrics for debugging and diagnostics"""
        watched_entries_count: int
        registered_watcher_count: int
        alias_count: int
        rpv_count: int
        var_count: int

    _trees: Dict[sdk.WatchableType, Any]
    _watchable_count: Dict[sdk.WatchableType, int]
    _global_watch_callbacks: Optional[GlobalWatchCallback]
    _global_unwatch_callbacks: Optional[GlobalUnwatchCallback]
    _logger: logging.Logger
    _tree_change_counters: Dict[sdk.WatchableType, int]
    _watchers: Dict[WatcherIdType, Watcher]
    _watched_entries: Dict[str, WatchableRegistryEntryNode]

    @staticmethod
    def split_path(path: str) -> List[str]:
        """Split a tree path in parts"""
        return [x for x in path.split('/') if x]

    @staticmethod
    def join_path(pieces: List[str]) -> str:
        """Merge tree path together"""
        return '/'.join([x for x in pieces if x])

    def __init__(self) -> None:
        self._trees = {
            sdk.WatchableType.Variable: {},
            sdk.WatchableType.Alias: {},
            sdk.WatchableType.RuntimePublishedValue: {}
        }
        self._tree_change_counters = {
            sdk.WatchableType.Variable: 0,
            sdk.WatchableType.Alias: 0,
            sdk.WatchableType.RuntimePublishedValue: 0
        }
        self._watchable_count = {
            sdk.WatchableType.Variable: 0,
            sdk.WatchableType.Alias: 0,
            sdk.WatchableType.RuntimePublishedValue: 0
        }

        self._watchers = {}
        self._watched_entries = {}
        self._global_watch_callbacks = None
        self._global_unwatch_callbacks = None
        self._logger = logging.getLogger(self.__class__.__name__)

    @enforce_thread(QT_THREAD_NAME)
    def _add_watchable(self, path: str, config: sdk.WatchableConfiguration) -> None:
        """Adds a single watchable to the tree storage"""
        parts = self.split_path(path)
        if len(parts) == 0:
            raise WatchableRegistryError(f"Empty path : {path}")
        node = self._trees[config.watchable_type]
        for i in range(len(parts) - 1):
            part = parts[i]
            if part not in node:
                node[part] = {}
            node = node[part]
        if parts[-1] in node:
            raise WatchableRegistryError(f"Cannot insert a watchable at location {path}. Another watchable already uses that path.")
        node[parts[-1]] = WatchableRegistryEntryNode(
            server_path=path,  # Required for proper error messages.
            config=config
        )
        self._watchable_count[config.watchable_type] += 1

    @enforce_thread(QT_THREAD_NAME)
    def _get_node(self, watchable_type: sdk.WatchableType, path: str) -> Union[WatchableRegistryNodeContent, WatchableRegistryEntryNode]:
        """Read a node in the tree and locks the tree while doing it."""
        parts = self.split_path(path)
        node = self._trees[watchable_type]
        for part in parts:
            if part not in node:
                raise WatchableRegistryNodeNotFoundError(f"Inexistent path : {path} ")
            node = node[part]

        if isinstance(node, dict):
            return WatchableRegistryNodeContent(
                watchables=dict((name, val.configuration) for name, val in node.items() if isinstance(val, WatchableRegistryEntryNode)),
                subtree=[name for name, val in node.items() if isinstance(val, dict)]
            )
        elif isinstance(node, WatchableRegistryEntryNode):
            return node
        else:
            raise WatchableRegistryError(f"Unexpected item of type {node.__class__.__name__} inside the registry")

    def broadcast_value_updates_to_watchers(self, updates: List[ValueUpdate]) -> None:
        for watcher_id, watcher in self._watchers.items():
            filtered_updates = [update for update in updates if update.watchable.server_id in watcher.subscribed_server_id]
            if len(filtered_updates) > 0:
                watcher.value_update_callback(watcher_id, filtered_updates)

    @enforce_thread(QT_THREAD_NAME)
    def register_watcher(self,
                         watcher_id: WatcherIdType,
                         value_update_callback: WatcherValueUpdateCallback,
                         unwatch_callback: UnwatchCallback,
                         ignore_duplicate: bool = False) -> None:
        # Create the Watcher first to validate the args
        watcher = Watcher(
            watcher_id=watcher_id,
            value_update_callback=value_update_callback,
            unwatch_callback=unwatch_callback
        )

        if watcher_id in self._watchers:
            if ignore_duplicate:
                return
            raise WatchableRegistryError(f"Duplicate watcher with ID {watcher_id}")

        self._watchers[watcher_id] = watcher

    @enforce_thread(QT_THREAD_NAME)
    def unregister_watcher(self, watcher_id: WatcherIdType) -> None:
        self.unwatch_all(watcher_id)

        with tools.SuppressException(KeyError):
            del self._watchers[watcher_id]

    def registered_watcher_count(self) -> int:
        """Return the number of active registered watchers"""
        return len(self._watchers)

    def watch_fqn(self, watcher_id: WatcherIdType, fqn: str) -> str:
        """Adds a watcher on the given watchable and register a callback to be 
        invoked when its value is updated 

        :param watcher_id: A string/int that identifies the owner of the callback. Passed back when the callback is invoked
        :param fqn: The watchable fully qualified name
        :return: The ID assigned to the value updates that will be broadcast for that item
        """
        parsed = self.FQN.parse(fqn)
        return self.watch(watcher_id, parsed.watchable_type, parsed.path)

    @enforce_thread(QT_THREAD_NAME)
    def watch(self, watcher_id: WatcherIdType, watchable_type: sdk.WatchableType, path: str) -> str:
        """Adds a watcher on the given watchable and register a callback to be 
        invoked when its value is updated 

        :param watcher_id: A string/int that identifies the owner of the callback. Passed back when the callback is invoked
        :param watchable_type: The watchable type
        :param path: The watchable tree path

        :return: The ID assigned to the value updates that will be broadcast for that item
        """
        watcher: Optional[Watcher] = None
        with tools.SuppressException(KeyError):
            watcher = self._watchers[watcher_id]

        if watcher is None:
            raise WatcherNotFoundError(f"No watchers with ID {watcher_id}")

        node = self._get_node(watchable_type, path)
        if not isinstance(node, WatchableRegistryEntryNode):
            raise WatchableRegistryError("Cannot watch something that is not a Watchable")

        self._watched_entries[node.configuration.server_id] = node
        added = False
        if node.configuration.server_id not in watcher.subscribed_server_id:
            watcher.subscribed_server_id.add(node.configuration.server_id)
            node.watcher_count += 1
            added = True

        if added and self._global_watch_callbacks is not None:
            self._global_watch_callbacks(watcher_id, node.server_path, node.configuration)

        return node.configuration.server_id

    @enforce_thread(QT_THREAD_NAME)
    def _unwatch_node_list(self, nodes: Iterable[WatchableRegistryEntryNode], watcher: Watcher) -> None:
        removed_list: List[WatchableRegistryEntryNode] = []
        for node in nodes:
            if node.configuration.server_id in watcher.subscribed_server_id:
                fqn = WatchableRegistry.FQN.make(node.configuration.watchable_type, node.server_path)
                try:
                    watcher.unwatch_callback(watcher.watcher_id, fqn, node.configuration)
                except Exception as e:
                    msg = f"Error in unwatch_callback callback for watcher ID {watcher.watcher_id} while unwatching {fqn}"
                    tools.log_exception(self._logger, e, msg)

                watcher.subscribed_server_id.remove(node.configuration.server_id)
                removed_list.append(node)
                node.watcher_count -= 1
                node.watcher_count = max(node.watcher_count, 0)
                if node.watcher_count == 0:
                    with tools.SuppressException(KeyError):
                        del self._watched_entries[node.configuration.server_id]

        # Callback is outside of lock on purpose to allow it to access the registry too. Deadlock will happen otherwise
        if self._global_unwatch_callbacks is not None:
            for node in removed_list:
                self._global_unwatch_callbacks(watcher.watcher_id, node.server_path, node.configuration)

    @enforce_thread(QT_THREAD_NAME)
    def unwatch_all(self, watcher_id: WatcherIdType) -> None:
        try:
            watcher = self._watchers[watcher_id]
        except KeyError:
            raise WatcherNotFoundError(f"No watchers with ID {watcher_id}")

        nodes: List[WatchableRegistryEntryNode] = []
        for server_id in watcher.subscribed_server_id:
            try:
                nodes.append(self._watched_entries[server_id])
            except KeyError as e:
                tools.log_exception(self._logger, e, "Missing node in watched_entry", str_level=logging.WARNING)

        self._unwatch_node_list(nodes, watcher)

    @enforce_thread(QT_THREAD_NAME)
    def unwatch(self, watcher_id: WatcherIdType, watchable_type: sdk.WatchableType, path: str) -> None:
        """Remove a the given watcher from the watcher list of the given node.

        :param watcher_id: A string/int that identifies the owner of the callback. Passed back when the callback is invoked
        :param watchable_type: The watchable type
        :param path: The watchable tree path
        """
        try:
            watcher = self._watchers[watcher_id]
        except KeyError:
            raise WatcherNotFoundError(f"No watchers with ID {watcher_id}")

        node = self._get_node(watchable_type, path)
        if not isinstance(node, WatchableRegistryEntryNode):
            raise WatchableRegistryError("Cannot unwatch something that is not a Watchable")

        self._unwatch_node_list([node], watcher)

    def unwatch_fqn(self, watcher_id: WatcherIdType, fqn: str) -> None:
        """Remove a the given watcher from the watcher list of the given node.

        :param watcher_id: A string/int that identifies the owner of the callback. Passed back when the callback is invoked
        :param watchable_type: The watchable type
        :param path: The watchable tree path
        """
        parsed = self.FQN.parse(fqn)
        self.unwatch(watcher_id, parsed.watchable_type, parsed.path)

    def watcher_count_by_server_id(self, server_id: str) -> int:
        """Return the number of watcher on a node, identified by its server_id

        :param server_id: The watchable server_id
        :return: The number of watchers 
        """
        try:
            entry = self._watched_entries[server_id]
        except KeyError:
            return 0
        return entry.watcher_count

    def node_watcher_count_fqn(self, fqn: str) -> Optional[int]:
        """Return the number of watcher on a node

        :param fqn: The watchable fully qualified name
        :return: The number of watchers
        """
        parsed = self.FQN.parse(fqn)
        return self.node_watcher_count(parsed.watchable_type, parsed.path)

    def node_watcher_count(self, watchable_type: sdk.WatchableType, path: str) -> Optional[int]:
        """Return the number of watcher on a node

        :param watchable_type: The watchable type
        :param path: The watchable tree path
        :return: The number of watchers
        """
        node = self._get_node(watchable_type, path)
        if not isinstance(node, WatchableRegistryEntryNode):
            self._logger.debug("Cannot get the watcher count of something that is not a Watchable")
            return None
        return node.watcher_count

    def watched_entries_count(self) -> int:
        """Return the total number of watchable being watched"""
        return len(self._watched_entries)

    @enforce_thread(QT_THREAD_NAME)
    def read(self, watchable_type: sdk.WatchableType, path: str) -> Optional[Union[WatchableRegistryNodeContent, sdk.WatchableConfiguration]]:
        """Read a node inside the registry.

        :watchable_type: The type of node to read
        :path: The tree path of the node

        :return: The node content. Either a watchable or a description of the subnodes
        """
        try:
            node = self._get_node(watchable_type, path)
            if isinstance(node, WatchableRegistryEntryNode):
                return node.configuration
        except WatchableRegistryNodeNotFoundError:
            return None
        except WatchableRegistryError as e:
            tools.log_exception(self._logger, e)
            return None
        return node

    def read_fqn(self, fqn: str) -> Optional[Union[WatchableRegistryNodeContent, sdk.WatchableConfiguration]]:
        """Read a node inside the registry using a fully qualified name.

        :param fqn: The fully qualified name created using ``make_fqn()``

        :return: The node content. Either a watchable or a description of the subnodes
        """
        parsed = self.FQN.parse(fqn)
        return self.read(parsed.watchable_type, parsed.path)

    def get_watchable_fqn(self, fqn: str) -> Optional[sdk.WatchableConfiguration]:
        node = self.read_fqn(fqn)
        if not isinstance(node, sdk.WatchableConfiguration):
            return None
        return node

    def is_watchable_fqn(self, fqn: str) -> bool:
        """Tells if the item referred to by the Fully Qualified Name exists and is a watchable.

        :param fqn: The fully qualified name created using ``make_fqn()``

        :return: ``True`` if exists and is a watchable
        """
        node = self.read_fqn(fqn)
        return isinstance(node, sdk.WatchableConfiguration)

    @enforce_thread(QT_THREAD_NAME)
    def write_content(self, data: Dict[sdk.WatchableType, Dict[str, sdk.WatchableConfiguration]]) -> None:
        """Write content of the given types.
        Triggers ``changed``.  May trigger ``filled`` if all types have data after calling this function.

        :param data: The data to add. Classified in dict[watchable_type][path]. 
        """
        touched = {
            sdk.WatchableType.Variable: False,
            sdk.WatchableType.Alias: False,
            sdk.WatchableType.RuntimePublishedValue: False,
        }
        for wt in data.keys():
            if len(data[wt]) > 0:
                self.clear_content_by_type(wt)

        for subdata in data.values():
            for path, wc in subdata.items():
                touched[wc.watchable_type] = True
                self._add_watchable(path, wc)

        for wt in touched:
            if touched[wt]:
                self._tree_change_counters[wt] += 1

    @enforce_thread(QT_THREAD_NAME)
    def clear_content_by_type(self, watchable_types: Union[sdk.WatchableType, Iterable[sdk.WatchableType]]) -> bool:
        """
        Clear the content of the given type from the registry. 
        May triggers ``changed`` and ``cleared`` if data was actually removed.

        :return: ``True`` if data was removed. ``False`` if the nothing was removed (already empty)
        """
        if isinstance(watchable_types, sdk.WatchableType):
            watchable_types = [watchable_types]
        self._logger.debug(f"Clearing content for types {watchable_types}")
        changed = False
        for watchable_type in watchable_types:
            had_data = len(self._trees[watchable_type]) > 0

            to_unwatch: List[WatchableRegistryEntryNode] = []
            for entry in self._watched_entries.values():
                if entry.configuration.watchable_type == watchable_type:
                    to_unwatch.append(entry)

            to_unwatch_per_watcher: Dict[WatcherIdType, List[WatchableRegistryEntryNode]] = {}
            for entry in to_unwatch:
                for watcher in self._watchers.values():
                    if entry.configuration.server_id in watcher.subscribed_server_id:
                        if watcher.watcher_id not in to_unwatch_per_watcher:
                            to_unwatch_per_watcher[watcher.watcher_id] = []
                        to_unwatch_per_watcher[watcher.watcher_id].append(entry)

            for watcher_id, node_list in to_unwatch_per_watcher.items():
                self._unwatch_node_list(node_list, self._watchers[watcher_id])

            for entry in to_unwatch:
                if entry.configuration.server_id in self._watched_entries:
                    self._logger.error(f"Inconsistency in Watchable Registry. Entry {entry.server_path} is still watched, but has no watcher")
                    del self._watched_entries[entry.configuration.server_id]    # Resilience on error

            if had_data:
                changed = True
                self._tree_change_counters[watchable_type] += 1
            self._trees[watchable_type] = {}
            self._watchable_count[watchable_type] = 0

        return changed

    def clear(self) -> bool:
        """
        Clear all the content from the registry.

        :return: ``True`` if data was removed. ``False`` if the nothing was removed (already empty) 
        """
        had_data = False
        for wt in [sdk.WatchableType.Variable, sdk.WatchableType.Alias, sdk.WatchableType.RuntimePublishedValue]:
            temp = self.clear_content_by_type(wt)
            had_data = had_data or temp

        if len(self._watched_entries) > 0:
            self._logger.critical("Failed to clear the registry properly. _watched_entries is not empty")

        for watcher in self._watchers.values():
            if len(watcher.subscribed_server_id) > 0:
                self._logger.critical(f"Failed to clear the registry properly. watcher {watcher.watcher_id} still have registered nodes")

        return had_data

    def has_data(self, watchable_type: sdk.WatchableType) -> bool:
        """Tells if there is data of the given type inside the registry

        :param watchable_type: The type of watchable to look for
        :return: ``True`` if there is data of that type. ``False otherwise``
        """
        return len(self._trees[watchable_type]) > 0

    def register_global_watch_callback(self, watch_callback: GlobalWatchCallback, unwatch_callback: GlobalUnwatchCallback) -> None:
        """Register a callback to be called whenever a new watcher is being added or removed on an entry

        :param watch_callback: Callback invoked on ``watch`` invocation
        :param unwatch_callback: Callback invoked on ``unwatch`` invocation
        """
        self._global_watch_callbacks = watch_callback
        self._global_unwatch_callbacks = unwatch_callback

    def get_change_counters(self) -> Dict[sdk.WatchableType, int]:
        return self._tree_change_counters.copy()

    def get_watchable_count(self, watchable_type: sdk.WatchableType) -> int:
        return self._watchable_count[watchable_type]

    def get_stats(self) -> Statistics:
        """Return internal performance metrics for diagnostic and debugging"""
        return self.Statistics(
            alias_count=self.get_watchable_count(sdk.WatchableType.Alias),
            rpv_count=self.get_watchable_count(sdk.WatchableType.RuntimePublishedValue),
            var_count=self.get_watchable_count(sdk.WatchableType.Variable),
            watched_entries_count=self.watched_entries_count(),
            registered_watcher_count=self.registered_watcher_count()
        )

    class FQN:
        @staticmethod
        def parse(fqn: str) -> ParsedFullyQualifiedName:
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
                path=fqn[colon_position + 1:]
            )

        @staticmethod
        def make(watchable_type: sdk.WatchableType, path: str) -> str:
            """Create a string representation that conveys enough information to find a specific element in the registry.
            Contains the type and the tree path. 

            :param watchable_type: The SDK watchable type
            :param path: The tree path

            :return: A fully qualified name containing the type and the tree path
            """
            return f"{TYPESTR_MAP_WT2S[watchable_type]}:{path}"

        @staticmethod
        def extend(fqn: str, pieces: Union[str, List[str]]) -> str:
            """Add one or many path parts to an existing Fully Qualified Name
            Ex. var:/a/b/c + ['x', 'y'] = var:/a/b/c/x/y

            :param fqn: The Fully Qualified Name to extend
            :param pieces: The parts to add
            """
            if isinstance(pieces, str):
                pieces = [pieces]
            parsed = WatchableRegistry.FQN.parse(fqn)
            path_parts = WatchableRegistry.split_path(parsed.path)
            prefix = ''
            if len(path_parts) > 0:
                index = parsed.path.find(path_parts[0])
                if index >= 0:
                    prefix = parsed.path[0:index]
            return WatchableRegistry.FQN.make(parsed.watchable_type, prefix + WatchableRegistry.join_path(path_parts + pieces))

        @staticmethod
        def is_equal(fqn1: str, fqn2: str) -> bool:
            """Compares 2 Fully Qualified Names and return ``True`` if they point to the same node

            :param fqn1: First operand
            :param fqn2: Second operand

            :return: ``True`` if equals
            """
            parsed1 = WatchableRegistry.FQN.parse(fqn1)
            parsed2 = WatchableRegistry.FQN.parse(fqn2)

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
