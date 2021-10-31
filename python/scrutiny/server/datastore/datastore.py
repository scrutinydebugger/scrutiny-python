import logging
from .datastore_entry import DatastoreEntry

class Datastore:

    MAX_ENTRY = 1000000 

    def __init__(self):
        self.entries = {}
        self.logger = logging.getLogger('scrutiny.'+self.__class__.__name__)
        self.watched_entries = set()

        self.entries_list_by_type = {}
        for entry_type in DatastoreEntry.Type:
            self.entries_list_by_type[entry_type] = []      

    def add_entries_quiet(self, entries):
        for entry in entries:
            try:
                self.add_entry(entry)
            except Exception as e:
                self.logger.debug(str(e))
                continue

    def add_entries(self, entries):
        for entry in entries:
           self.add_entry(entry)

    def add_entry(self, entry):
        if entry.get_id() in self.entries:
            raise ValueError('Duplicate datastore entry')
        
        if len(self.entries) >= self.MAX_ENTRY:
            raise RuntimeError('Datastore cannot have more than %d entries' % self.MAX_ENTRY)

        self.entries[entry.get_id()] = entry;
        self.entries_list_by_type[entry.get_type()].append(entry)

    def get_entry(self, entry_id):
        return self.entries[entry_id]

    def start_watching(self, entry_id, callback_owner, callback, args=None):
        entry_id = self.interpret_entry_id(entry_id)
        entry = self.get_entry(entry_id)
        self.watched_entries.add(entry_id)
        if not entry.has_value_change_callback(callback_owner):
            entry.register_value_change_callback(owner=callback_owner, callback=callback, args=args)

    def stop_watching(self, entry_id, callback_owner):
        entry_id = self.interpret_entry_id(entry_id)
        entry = self.get_entry(entry_id)
        try:
            self.watched_entries.remove(entry_id)
        except:
            pass
        entry.unregister_value_change_callback(callback_owner)

    def get_all_entries(self):
        for entry_id in self.entries:
            yield self.entries[entry_id]

    def get_entries_list_by_type(self, wtype):
        return self.entries_list_by_type[wtype]

    def interpret_entry_id(self, entry_id):
        if isinstance(entry_id, DatastoreEntry):
            return entry.get_id()
        else:
            return entry_id

    def get_entries_count(self, wtype=None):
        val = 0
        for entry_type in self.entries_list_by_type:
            if wtype is None or wtype == entry_type:
                val += len(self.entries_list_by_type[entry_type])

        return val

    def set_value(self, entry_id, value):
        entry_id = self.interpret_entry_id(entry_id)
        entry = self.get_entry(entry_id)
        entry.set_value(value)

    def get_watched_entries(self):
        return self.watched_entries

    def clear(self):
        self.__init__()
