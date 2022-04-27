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

from typing import Set, List, Dict, Optional, Any, Iterator, Union


class Datastore:
    logger: logging.Logger
    entries: Dict[str, DatastoreEntry]
    watched_entries: Set[str]
    entries_list_by_type: Dict[DatastoreEntry.EntryType, List[DatastoreEntry]]

    MAX_ENTRY: int = 1000000

    def __init__(self):
        self.logger = logging.getLogger('scrutiny.' + self.__class__.__name__)
        self.clear()

    def clear(self) -> None:
        self.entries = {}
        self.watched_entries = set()

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

    def start_watching(self, entry_id: str, callback_owner: str, callback: GenericCallback, args: Any = None) -> None:
        entry_id = self.interpret_entry_id(entry_id)
        entry = self.get_entry(entry_id)
        self.watched_entries.add(entry_id)
        if not entry.has_value_change_callback(callback_owner):
            entry.register_value_change_callback(owner=callback_owner, callback=callback, args=args)

    def stop_watching(self, entry_id: str, callback_owner: str) -> None:
        entry_id = self.interpret_entry_id(entry_id)
        entry = self.get_entry(entry_id)
        try:
            self.watched_entries.remove(entry_id)
        except:
            pass
        entry.unregister_value_change_callback(callback_owner)

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

    def get_watched_entries(self) -> Set[str]:
        return self.watched_entries
