import logging
from .datastore_entry import DatastoreEntry

import logging

class Datastore:
    def __init__(self):
        self.entries = {}
        self.logger = logging.getLogger('datastore')
        self.watched_entries = set()

    def add_entries_quiet(self, entries):
        for entry in entries:
            try:
                self.add_entry(entry)
            except:
                continue

    def add_entry(self, entry):
        if entry.get_id() in self.entries:
            raise ValueError('Duplicate datastore entry')

        self.entries[entry.get_id()] = entry;

    def get_entry(self, entry_id):
        return self.entries[entry_id]

    def start_watching(self, entry_id, dirty_callback=None, args=None):
        entry_id = self.interpret_entry_id(entry_id)
        entry = self.get_entry(entry_id)
        self.watched_entries.add(entry_id)
        entry.watch(dirty_callback, args)

    def stop_watching(self, entry_id):
        entry_id = self.interpret_entry_id(entry_id)
        entry = self.get_entry(entry_id)
        try:
            self.watched_entries.remove(entry_id)
        except:
            pass
        entry.stop_watching(False)

    def get_dirty_entries(self):
        entries = []
        for entry_id in self.watched_entries:
            entry = self.get_entry(entry_id)
            if entry.is_dirty():
                entries.append(entry)
        return entries

    def get_all_entries(self):
        for entry_id in self.entries:
            yield self.entries[entry_id]

    def interpret_entry_id(self, entry_id):
        if isinstance(entry_id, DatastoreEntry):
            return entry.get_id()
        else:
            return entry_id

