#    datastore.py
#        This class is a container that will hold all the data read from a device (e.g. the
#        variables).
#        It's the meeting point of the API (with ValueStreamer) and the DeviceHandler
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import logging
from .datastore_entry import DatastoreEntry, EntryType, UpdateTargetRequest
from scrutiny.core.typehints import GenericCallback

from typing import Set, List, Dict, Optional, Any, Iterator, Union, Callable


class WatchCallback(GenericCallback):
    callback: Callable[[str], None]


class Datastore:
    logger: logging.Logger
    entries: Dict[EntryType, Dict[str, DatastoreEntry]]
    watcher_map: Dict[EntryType, Dict[str, Set[str]]]
    global_watch_callbacks: List[WatchCallback]
    global_unwatch_callbacks: List[WatchCallback]

    MAX_ENTRY: int = 1000000

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.global_watch_callbacks = []
        self.global_unwatch_callbacks = []

        self.entries = {}
        self.watcher_map = {}
        for entry_type in EntryType:
            self.entries[entry_type] = {}
            self.watcher_map[entry_type] = {}

    def clear(self, entry_type: Optional[EntryType] = None) -> None:
        if entry_type is None:
            type_to_clear_list = list(EntryType.__iter__())
        else:
            type_to_clear_list = [entry_type]

        for type_to_clear in type_to_clear_list:
            self.entries[type_to_clear] = {}
            self.watcher_map[type_to_clear] = {}

    def add_entries_quiet(self, entries: List[DatastoreEntry]):
        for entry in entries:
            self.add_entry_quiet(entry)

    def add_entry_quiet(self, entry: DatastoreEntry):
        try:
            self.add_entry(entry)
        except Exception as e:
            self.logger.debug(str(e))

    def add_entries(self, entries: List[DatastoreEntry]) -> None:
        for entry in entries:
            self.add_entry(entry)

    def add_entry(self, entry: DatastoreEntry) -> None:
        entry_id = entry.get_id()
        for entry_type in EntryType:
            if entry_id in self.entries[entry_type]:
                raise ValueError('Duplicate datastore entry')

        if self.get_entries_count() >= self.MAX_ENTRY:
            raise RuntimeError('Datastore cannot have more than %d entries' % self.MAX_ENTRY)

        self.entries[entry.get_type()][entry.get_id()] = entry

    def get_entry(self, entry_id: str) -> DatastoreEntry:
        for entry_type in EntryType:
            if entry_id in self.entries[entry_type]:
                return self.entries[entry_type][entry_id]
        raise KeyError('Entry with ID %s not found in datastore' % entry_id)

    def add_watch_callback(self, callback: WatchCallback):
        # Mainly used to notify device handler that a new variable is to be polled
        self.global_watch_callbacks.append(callback)

    def add_unwatch_callback(self, callback: WatchCallback):
        self.global_unwatch_callbacks.append(callback)

    def start_watching(self, entry_id: Union[DatastoreEntry, str], watcher: str, value_update_callback: Optional[GenericCallback] = None, target_update_callback: Optional[GenericCallback] = None, args: Any = None) -> None:
        # Shortcut for unit tests
        if value_update_callback is None:
            value_update_callback = GenericCallback(lambda *args, **kwargs: None)

        if target_update_callback is None:
            target_update_callback = GenericCallback(lambda *args, **kwargs: None)

        entry_id = self.interpret_entry_id(entry_id)
        entry = self.get_entry(entry_id)
        if entry_id not in self.watcher_map[entry.get_type()]:
            self.watcher_map[entry.get_type()][entry.get_id()] = set()
        self.watcher_map[entry.get_type()][entry_id].add(watcher)

        if not entry.has_value_change_callback(watcher):
            entry.register_value_change_callback(owner=watcher, callback=value_update_callback, args=args)

        if not entry.has_target_update_callback(watcher):
            entry.register_target_update_callback(owner=watcher, callback=target_update_callback, args=args)

        # Mainly used to notify device handler that a new variable is to be polled
        for callback in self.global_watch_callbacks:
            callback(entry_id)

    def is_watching(self, entry: Union[DatastoreEntry, str], watcher: str) -> bool:
        entry_id = self.interpret_entry_id(entry)
        entry = self.get_entry(entry_id)
        if entry_id not in self.watcher_map[entry.get_type()]:
            return False
        return watcher in self.watcher_map[entry.get_type()][entry_id]

    def get_watchers(self, entry: Union[DatastoreEntry, str]) -> List[str]:
        entry_id = self.interpret_entry_id(entry)
        entry = self.get_entry(entry_id)
        if entry_id not in self.watcher_map[entry.get_type()]:
            return []
        return list(self.watcher_map[entry.get_type()][entry_id])

    def stop_watching(self, entry_id: Union[DatastoreEntry, str], watcher: str) -> None:
        entry_id = self.interpret_entry_id(entry_id)
        entry = self.get_entry(entry_id)

        try:
            self.watcher_map[entry.get_type()][entry_id].remove(watcher)
        except:
            pass

        try:
            if len(self.watcher_map[entry.get_type()][entry_id]) == 0:
                del self.watcher_map[entry.get_type()][entry_id]
        except:
            pass

        entry.unregister_value_change_callback(watcher)
        entry.unregister_target_update_callback(watcher)

        for callback in self.global_unwatch_callbacks:
            callback(entry_id)

    def get_all_entries(self, entry_type: Optional[EntryType] = None) -> Iterator[DatastoreEntry]:
        for entry_type in EntryType:
            for entry_id in self.entries[entry_type]:
                yield self.entries[entry_type][entry_id]

    def get_entries_list_by_type(self, entry_type: EntryType) -> List[DatastoreEntry]:
        return list(self.entries[entry_type].values())

    def interpret_entry_id(self, entry_id: Union[DatastoreEntry, str]) -> str:
        if isinstance(entry_id, DatastoreEntry):
            return entry_id.get_id()
        else:
            return entry_id

    def get_entries_count(self, entry_type: Optional[EntryType] = None) -> int:
        val = 0
        typelist = [entry_type] if entry_type is not None else list(EntryType.__iter__())
        for thetype in typelist:
            val += len(self.entries[thetype])

        return val

    def set_value(self, entry_id: Union[DatastoreEntry, str], value: Any) -> None:
        entry_id = self.interpret_entry_id(entry_id)
        entry = self.get_entry(entry_id)
        entry.set_value(value)

    def update_target_value(self, entry_id: Union[DatastoreEntry, str], value: Any) -> UpdateTargetRequest:
        entry_id = self.interpret_entry_id(entry_id)
        entry = self.get_entry(entry_id)
        return entry.update_target_value(value)

    def get_watched_entries_id(self, entry_type: EntryType) -> List[str]:
        return list(self.watcher_map[entry_type].keys())
