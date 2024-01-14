#    datastore.py
#        This class is a container that will hold all the data read from a device (e.g. the
#        variables).
#        It's the meeting point of the API (with ValueStreamer) and the DeviceHandler
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import logging
import functools
from scrutiny.server.datastore.datastore_entry import *
from scrutiny.server.datastore.entry_type import EntryType

from scrutiny.core.typehints import GenericCallback

from typing import Callable, List, Dict, Generator, Set, List, Optional, Union, Any


class WatchCallback(GenericCallback):
    callback: Callable[[str], None]     # str is the owner


class Datastore:
    """
    Class at the center of the server. It contains the value of all watched items.
    the device handler writes variable and RPV (Runtime Published Values) into the datastore
    and the user subscribe to value change by setting a callback in the datastore through the API.

    The datastore manages entries per type. There is 3 types : Variable, RPV, Alias.
    We can do most operation on all entries of one type. This per-type management is required because
    from the outside, there are differences. Mainly, RPV are added and removed to the datastore by the device
    handler when a connection is made. Aliases and variables are added when a Firmware Description is loaded. 
    It's the same as having 3 datastore, one for each type.
    """

    logger: logging.Logger
    entries: Dict[EntryType, Dict[str, DatastoreEntry]]
    displaypath2idmap: Dict[EntryType, Dict[str, str]]
    watcher_map: Dict[EntryType, Dict[str, Set[str]]]
    global_watch_callbacks: List[WatchCallback]
    global_unwatch_callbacks: List[WatchCallback]
    target_update_request_queue: "List[UpdateTargetRequest]"

    MAX_ENTRY: int = 1000000

    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.global_watch_callbacks = []    # When somebody starts watching an entry,m these callbacks are called
        self.global_unwatch_callbacks = []  # When somebody stops watching an entry, these callbacks are called

        self.entries = {}
        self.watcher_map = {}
        self.displaypath2idmap = {}
        self.target_update_request_queue = []
        for entry_type in EntryType.all():
            self.entries[entry_type] = {}
            self.watcher_map[entry_type] = {}
            self.displaypath2idmap[entry_type] = {}

    def clear(self, entry_type: Optional[EntryType] = None) -> None:
        """ Deletes all entries of a given type. All types if None"""
        if entry_type is None:
            type_to_clear_list = EntryType.all()
        else:
            type_to_clear_list = [entry_type]

        for type_to_clear in type_to_clear_list:
            self.entries[type_to_clear] = {}
            self.watcher_map[type_to_clear] = {}
            self.displaypath2idmap[type_to_clear] = {}

    def add_entries_quiet(self, entries: List[DatastoreEntry]) -> None:
        """ Add many entries without raising exceptions. Silently remove failing ones"""
        for entry in entries:
            self.add_entry_quiet(entry)

    def add_entry_quiet(self, entry: DatastoreEntry) -> None:
        """ Add a single entry without raising exception. Silently remove failing ones"""
        try:
            self.add_entry(entry)
        except Exception as e:
            self.logger.debug(str(e))

    def add_entries(self, entries: List[DatastoreEntry]) -> None:
        """ Add multiple entries to the datastore"""
        for entry in entries:
            self.add_entry(entry)

    def add_entry(self, entry: DatastoreEntry) -> None:
        """ Add a single entry to the datastore."""
        entry_id = entry.get_id()
        for entry_type in EntryType.all():
            if entry_id in self.entries[entry_type]:
                raise ValueError('Duplicate datastore entry')

        if self.get_entries_count() >= self.MAX_ENTRY:
            raise RuntimeError('Datastore cannot have more than %d entries' % self.MAX_ENTRY)

        if isinstance(entry, DatastoreAliasEntry):
            resolved_entry = entry.resolve()
            if resolved_entry.get_id() not in self.entries[resolved_entry.get_type()]:
                raise KeyError('Alias ID %s (%s) refer to entry ID %s (%s) that is not in the datastore' %
                               (entry.get_id(), entry.get_display_path(), resolved_entry.get_id(), resolved_entry.get_display_path()))

        self.entries[entry.get_type()][entry.get_id()] = entry
        self.displaypath2idmap[entry.get_type()][entry.get_display_path()] = entry.get_id()

    def get_entry(self, entry_id: str) -> DatastoreEntry:
        """ Fetch a datastore entry by its ID"""
        for entry_type in EntryType.all():
            if entry_id in self.entries[entry_type]:
                return self.entries[entry_type][entry_id]
        raise KeyError('Entry with ID %s not found in datastore' % entry_id)

    def get_entry_by_display_path(self, display_path: str) -> DatastoreEntry:
        """ Find an entry by its display path, which is supposed to be unique"""
        for entry_type in EntryType.all():
            if display_path in self.displaypath2idmap[entry_type]:
                entry_id = self.displaypath2idmap[entry_type][display_path]
                if entry_id in self.entries[entry_type]:
                    return self.entries[entry_type][entry_id]

        raise KeyError('Entry with display path %s not found in datastore' % display_path)

    def add_watch_callback(self, callback: WatchCallback) -> None:
        """ Mainly used to notify device handler that a new variable is to be polled"""
        self.global_watch_callbacks.append(callback)

    def add_unwatch_callback(self, callback: WatchCallback) -> None:
        self.global_unwatch_callbacks.append(callback)

    def start_watching(self,
                       entry_id: Union[DatastoreEntry, str],
                       watcher: str,
                       value_change_callback: Optional[GenericCallback] = None,
                       target_update_callback: Optional[GenericCallback] = None
                       ) -> None:
        """ 
        Register a new callback on the entry identified by the given entry_id.
        The watcher parameter will be given back when calling the callback.
        We ensure to call the callback for each watcher.
        """

        if value_change_callback is None:   # No callback mainly happens with unit tests
            value_change_callback = GenericCallback(lambda *args, **kwargs: None)

        if target_update_callback is None:  # No callback mainly happens with unit tests
            target_update_callback = GenericCallback(lambda *args, **kwargs: None)

        entry_id = self.interpret_entry_id(entry_id)
        entry = self.get_entry(entry_id)

        if entry_id not in self.watcher_map[entry.get_type()]:
            self.watcher_map[entry.get_type()][entry.get_id()] = set()
        self.watcher_map[entry.get_type()][entry_id].add(watcher)

        if not entry.has_value_change_callback(watcher):
            entry.register_value_change_callback(owner=watcher, callback=value_change_callback)

        # Mainly used to notify device handler that a new variable is to be polled
        for callback in self.global_watch_callbacks:
            callback(entry_id)

        if isinstance(entry, DatastoreAliasEntry):
            # Alias are tricky. When we subscribe to them, another hidden subscription to the referenced entry is made here
            alias_value_change_callback = functools.partial(self.alias_value_change_callback, watching_entry=entry)
            self.start_watching(
                entry_id=entry.resolve(),
                watcher=self.make_owner_from_alias_entry(entry),
                value_change_callback=GenericCallback(alias_value_change_callback)
            )

    def is_watching(self, entry: Union[DatastoreEntry, str], watcher: str) -> bool:
        """ Tell if the given watcher is actually watching an entry"""
        entry_id = self.interpret_entry_id(entry)
        entry = self.get_entry(entry_id)
        if entry_id not in self.watcher_map[entry.get_type()]:
            return False
        return watcher in self.watcher_map[entry.get_type()][entry_id]

    def get_watchers(self, entry: Union[DatastoreEntry, str]) -> List[str]:
        """ Get the list of watchers on a given entry"""
        entry_id = self.interpret_entry_id(entry)
        entry = self.get_entry(entry_id)
        if entry_id not in self.watcher_map[entry.get_type()]:
            return []
        return list(self.watcher_map[entry.get_type()][entry_id])

    def stop_watching(self, entry_id: Union[DatastoreEntry, str], watcher: str) -> None:
        """ Remove the callback for a given watcher on a given entry"""
        entry_id = self.interpret_entry_id(entry_id)
        entry = self.get_entry(entry_id)

        try:
            self.watcher_map[entry.get_type()][entry_id].remove(watcher)
        except Exception:
            pass

        try:
            if len(self.watcher_map[entry.get_type()][entry_id]) == 0:
                del self.watcher_map[entry.get_type()][entry_id]

                if isinstance(entry, DatastoreAliasEntry):
                    # Special handling for Aliases.
                    # If nobody watches this alias, then we can remove the internal subscription to the referenced entry
                    self.stop_watching(entry.resolve(), self.make_owner_from_alias_entry(entry))
        except Exception:
            pass

        entry.unregister_value_change_callback(watcher)

        for callback in self.global_unwatch_callbacks:
            callback(entry_id)  # Mainly used by the device handler to know it can stop polling that entry

    def stop_watching_all(self, watcher: str) -> None:
        for entry_type in EntryType.all():
            watched_entries_id = self.get_watched_entries_id(entry_type)    # Make a copy of the list
            for entry_id in watched_entries_id:
                self.stop_watching(entry_id, watcher)

    def get_all_entries(self, entry_type: Optional[EntryType] = None) -> Generator[DatastoreEntry, None, None]:
        """ Fetch all entries of a given type. All types if None"""
        entry_types = EntryType.all() if entry_type is None else [entry_type]
        for entry_type in entry_types:
            for entry_id in self.entries[entry_type]:
                yield self.entries[entry_type][entry_id]

    def interpret_entry_id(self, entry_id: Union[DatastoreEntry, str]) -> str:
        """ Get the entry ID of a given entry."""
        if isinstance(entry_id, DatastoreEntry):
            return entry_id.get_id()
        else:
            return entry_id

    def get_entries_count(self, entry_type: Optional[EntryType] = None) -> int:
        """ Returns the number of entries of a given type. All types if None"""
        val = 0
        typelist = [entry_type] if entry_type is not None else EntryType.all()
        for thetype in typelist:
            val += len(self.entries[thetype])

        return val

    def set_value(self, entry_id: Union[DatastoreEntry, str], value: Any) -> None:
        """ Sets the value on an entry"""
        entry_id = self.interpret_entry_id(entry_id)
        entry = self.get_entry(entry_id)
        entry.set_value(value)

    def update_target_value(self, entry_id: Union[DatastoreEntry, str], value: Any, callback: UpdateTargetRequestCallback) -> UpdateTargetRequest:
        """Enqueue a write request on the datastore entry. Will be picked up by the device side to be executed"""
        if isinstance(entry_id, DatastoreEntry):
            entry = entry_id
        else:
            entry = self.get_entry(entry_id)
        update_request = UpdateTargetRequest(value, entry=entry, callback=callback)

        if isinstance(entry, DatastoreAliasEntry):
            new_value = entry.aliasdef.compute_user_to_device(value)
            nested_callback = UpdateTargetRequestCallback(functools.partial(self.alias_target_update_callback, update_request))
            new_request = self.update_target_value(entry.resolve(), new_value, callback=nested_callback)
            if new_request.is_complete():  # Edge case if failed to enqueue request.
                new_request.complete(success=update_request.is_complete())
            return update_request
        else:
            self.target_update_request_queue.append(update_request)

        return update_request

    def alias_target_update_callback(self, alias_request: UpdateTargetRequest, success: bool, entry: DatastoreEntry, timestamp: float) -> None:
        """Callback used by an alias to grab the result of the target update and apply it to its own"""
        # entry is a var or a RPV
        alias_request.complete(success=success)

    def pop_target_update_request(self) -> Optional[UpdateTargetRequest]:
        """ Returns the next write request to be processed and removes it form the queue"""
        try:
            return self.target_update_request_queue.pop(0)
        except IndexError:
            return None

    def peek_target_update_request(self) -> Optional[UpdateTargetRequest]:
        """ Returns the next write request to be processed without removing it from the queue"""
        try:
            return self.target_update_request_queue[0]
        except IndexError:
            return None

    def has_pending_target_update(self) -> bool:
        return len(self.target_update_request_queue) > 0

    def get_pending_target_update_count(self) -> int:
        return len(self.target_update_request_queue)

    def get_watched_entries_id(self, entry_type: EntryType) -> List[str]:
        """ Get a list of all watched entries ID of a given type."""
        return list(self.watcher_map[entry_type].keys())

    def make_owner_from_alias_entry(self, entry: DatastoreAliasEntry) -> str:
        """ When somebody subscribes to an alias, the datastore starts watching the pointed entry
        This method creates a watcher name based on the alias ID"""
        return 'alias_' + entry.get_id()

    def alias_value_change_callback(self, owner: str, entry: DatastoreEntry, watching_entry: DatastoreAliasEntry) -> None:
        """ This callback is the one given when the datastore starts watching an entry because somebody wants to watch an alias."""
        watching_entry.set_value_internal(entry.get_value())

    @classmethod
    def is_rpv_path(cls, path: str) -> bool:
        """Returns True if the tree-like path matches the expected RPV default path (i.e. /rpv/x1234)"""
        return DatastoreRPVEntry.is_valid_path(path)
