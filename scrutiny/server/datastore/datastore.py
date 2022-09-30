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
from scrutiny.server.datastore.datastore_entry import *
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
            type_to_clear_list = EntryType.all()
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
        
        if isinstance(entry, DatastoreAliasEntry):
            resolved_entry = entry.resolve()
            if resolved_entry.get_id() not in self.entries[resolved_entry.get_type()]:
                raise KeyError('Alias ID %s (%s) refer to entry ID %s (%s) that is not in the datastore' % (entry.get_id(), entry.get_display_path(), resolved_entry.get_id(), resolved_entry.get_display_path()))

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

    def start_watching(self, entry_id: Union[DatastoreEntry, str], watcher: str, value_change_callback: Optional[GenericCallback] = None, target_update_callback: Optional[GenericCallback] = None, args: Any = None) -> None:
        # Shortcut for unit tests
        if value_change_callback is None:
            value_change_callback = GenericCallback(lambda *args, **kwargs: None)

        if target_update_callback is None:
            target_update_callback = GenericCallback(lambda *args, **kwargs: None)

        entry_id = self.interpret_entry_id(entry_id)
        entry = self.get_entry(entry_id)

        if entry_id not in self.watcher_map[entry.get_type()]:
            self.watcher_map[entry.get_type()][entry.get_id()] = set()
        self.watcher_map[entry.get_type()][entry_id].add(watcher)

        if not entry.has_value_change_callback(watcher):
            entry.register_value_change_callback(owner=watcher, callback=value_change_callback, args=args)

        # Mainly used to notify device handler that a new variable is to be polled
        for callback in self.global_watch_callbacks:
            callback(entry_id)
        
        if isinstance(entry, DatastoreAliasEntry):
            self.start_watching(
                entry_id = entry.resolve(), 
                watcher = self.make_owner_from_alias_entry(entry),
                value_change_callback = GenericCallback(self.alias_value_change_callback),
                args = {'watching_entry' : entry}
                )

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

                if isinstance(entry, DatastoreAliasEntry):
                    self.stop_watching(entry.resolve(), self.make_owner_from_alias_entry(entry))
        except:
            pass

        entry.unregister_value_change_callback(watcher)

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
        typelist = [entry_type] if entry_type is not None else EntryType.all()
        for thetype in typelist:
            val += len(self.entries[thetype])

        return val

    def set_value(self, entry_id: Union[DatastoreEntry, str], value: Any) -> None:
        entry_id = self.interpret_entry_id(entry_id)
        entry = self.get_entry(entry_id)
        entry.set_value(value)

    def update_target_value(self, entry_id: Union[DatastoreEntry, str], value: Any, callback:UpdateTargetRequestCallback) -> UpdateTargetRequest:
        entry_id = self.interpret_entry_id(entry_id)
        entry = self.get_entry(entry_id)
        return entry.update_target_value(value, callback=callback)

    def get_watched_entries_id(self, entry_type: EntryType) -> List[str]:
        return list(self.watcher_map[entry_type].keys())

    def make_owner_from_alias_entry(self, entry:DatastoreAliasEntry) -> str:
        return 'alias_' + entry.get_id()

    def alias_value_change_callback(self, owner: str, args: Any, entry: DatastoreEntry) -> None:
        watching_entry:DatastoreAliasEntry = args['watching_entry']
        watching_entry.set_value_internal(entry.get_value())
    
    @classmethod
    def is_rpv_path(cls, path:str) -> bool:
        return DatastoreRPVEntry.is_valid_path(path)
