#    datastore.py
#        This class is a container that will hold all the data read from a device (e.g. the
#        variables).
#        It's the meeting point of the API (with ValueStreamer) and the DeviceHandler
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import logging
from .datastore_entry import DatastoreEntry
from scrutiny.core.typehints import GenericCallback

from typing import Set, List, Dict, Optional, Any, Iterator, Union, Callable

class WatchCallback(GenericCallback):
    callback: Callable[[str], None]

class Datastore:
    logger: logging.Logger
    entries: Dict[str, DatastoreEntry]
    entries_list_by_type: Dict[DatastoreEntry.EntryType, List[DatastoreEntry]]
    global_watch_callbacks:List[WatchCallback]
    global_unwatch_callbacks:List[WatchCallback]
    watcher_map:Dict[str, Set[str]]

    MAX_ENTRY: int = 1000000

    def __init__(self):
        self.logger = logging.getLogger('scrutiny.' + self.__class__.__name__)
        self.global_watch_callbacks = []
        self.global_unwatch_callbacks = []
        self.clear()

    def clear(self) -> None:
        self.entries = {}
        self.watcher_map = {}

        self.entries_list_by_type = {}
        for entry_type in DatastoreEntry.EntryType:
            self.entries_list_by_type[entry_type] = []

    def add_entries_quiet(self, entries: List[DatastoreEntry]):
        for entry in entries:
            try:
                self.add_entry(entry)
            except Exception as e:
                self.logger.debug(str(e))
                continue

    def add_entries(self, entries: List[DatastoreEntry]) -> None:
        for entry in entries:
            self.add_entry(entry)

    def add_entry(self, entry: DatastoreEntry) -> None:
        if entry.get_id() in self.entries:
            raise ValueError('Duplicate datastore entry')

        if len(self.entries) >= self.MAX_ENTRY:
            raise RuntimeError('Datastore cannot have more than %d entries' % self.MAX_ENTRY)

        self.entries[entry.get_id()] = entry;
        self.entries_list_by_type[entry.get_type()].append(entry)

    def get_entry(self, entry_id: str) -> DatastoreEntry:
        return self.entries[entry_id]

    def add_watch_callback(self, callback:WatchCallback):
        self.global_watch_callbacks.append(callback)

    def add_unwatch_callback(self, callback:WatchCallback):
        self.global_unwatch_callbacks.append(callback)

    def start_watching(self, entry_id: str, watcher: str, callback: GenericCallback, args: Any = None) -> None:
        entry_id = self.interpret_entry_id(entry_id)
        entry = self.get_entry(entry_id)
        if entry_id not in self.watcher_map:
            self.watcher_map[entry.get_id()] = set()
        self.watcher_map[entry_id].add(watcher)
        if not entry.has_value_change_callback(watcher):
            entry.register_value_change_callback(owner=watcher, callback=callback, args=args)

        for callback in self.global_watch_callbacks:
            callback(entry_id)

    def stop_watching(self, entry_id: str, watcher: str) -> None:
        entry_id = self.interpret_entry_id(entry_id)
        entry = self.get_entry(entry_id)
        
        try:
            self.watcher_map[entry_id].remove(watcher)
        except:
            pass

        try:
            if len(self.watcher_map[entry_id]) == 0:
                del self.watcher_map[entry_id]
        except:
            pass
        
        entry.unregister_value_change_callback(watcher)
        for callback in self.global_unwatch_callbacks:
            callback(entry_id)

    def get_all_entries(self) -> Iterator[DatastoreEntry]:
        for entry_id in self.entries:
            yield self.entries[entry_id]

    def get_entries_list_by_type(self, wtype: DatastoreEntry.EntryType) -> List[DatastoreEntry]:
        return self.entries_list_by_type[wtype]

    def interpret_entry_id(self, entry_id: Union[DatastoreEntry, str]):
        if isinstance(entry_id, DatastoreEntry):
            return entry_id.get_id()
        else:
            return entry_id

    def get_entries_count(self, wtype: Optional[DatastoreEntry.EntryType] = None):
        val = 0
        for entry_type in self.entries_list_by_type:
            if wtype is None or wtype == entry_type:
                val += len(self.entries_list_by_type[entry_type])

        return val

    def set_value(self, entry_id: str, value: Any) -> None:
        entry_id = self.interpret_entry_id(entry_id)
        entry = self.get_entry(entry_id)
        entry.set_value(value)

    def get_watched_entries_id(self) -> Set[str]:
        return list(self.watcher_map.keys())

    def get_watchers(self, entry_id:Union[DatastoreEntry, str]) -> Set[str]:
        entry_id = self.interpret_entry_id(entry_id)
        if entry_id not in self.watcher_map:
            return set()
        else:
            return set(self.watcher_map[entry_id]) # Make a copy

