import unittest
from server.datastore import Datastore
from server.datastore import DatastoreEntry

class TestDataStore(unittest.TestCase):
    def setUp(self):
        self.callback_call_history = {}


    def make_dummy_entries(self, n):
        for i in range(n):
            entry = DatastoreEntry(DatastoreEntry.Type.eVar, 'path_%d' %i)
            yield entry

    def entry_callback(self, entry, arg):
        if entry.get_id() not in self.callback_call_history:
            self.callback_call_history[entry.get_id()] = 0
        self.callback_call_history[entry.get_id()]+=1

    def assertCallbackCalled(self, entry_id, n):
        if isinstance(entry_id, DatastoreEntry):
            entry_id = entry_id.get_id()

        if entry_id not in self.callback_call_history:
            count =0
        else:
            count = self.callback_call_history[entry_id]
        self.assertEqual(count, n)

    def test_add_get(self):
        n = 4;
        ds = Datastore()
        entries = list(self.make_dummy_entries(n))
        for entry in entries:
            ds.add_entry(entry)

        ds_entries = list(ds.get_all_entries())
        self.assertEqual(len(ds_entries), n)
        for entry in ds_entries:
            self.assertIn(entry, entries)

    def test_entry_no_duplicate_id(self):
        n = 10000
        entries = self.make_dummy_entries(n)
        entry_ids = {}
        for entry in entries:
            self.assertNotIn(entry.get_id(), entry_ids)
            entry_ids[entry.get_id()] = 0

    def test_get_dirty_only_when_watched(self):
        n = 10
        ntowatch = 5
        ndirty = 2

        ds = Datastore()
        entries = list(self.make_dummy_entries(n))
        for entry in entries:
            entry.set_dirty()
        ds.add_entries_quiet(entries)

        # Check that we get no dirty entry if we don't watch
        dirty_entries = ds.get_dirty_entries()
        self.assertEqual(len(dirty_entries), 0)
        for i in range(ntowatch):
            ds.start_watching(entries[i].get_id())

        # Check that we don't get dirty entrie that are unwatched
        dirty_entries = ds.get_dirty_entries()
        self.assertEqual(len(dirty_entries), ntowatch)
        
        for i in range(n):
            if i>=ndirty:
                entries[i].set_dirty(False)

        # Check that we get only dirty entries even if we watch more
        dirty_entries = ds.get_dirty_entries()
        self.assertEqual(len(dirty_entries), ndirty)
    

    # Make sure all callbacks are called when entry gets dirty
    def test_callback_on_dirty(self):
        entries = list(self.make_dummy_entries(5))
        ds = Datastore()
        ds.add_entries_quiet(entries)
        for entry in entries:
            ds.start_watching(entry.get_id(), self.entry_callback, dict(someParam=entry.get_id()))
        
        for entry in entries:
            self.assertCallbackCalled(entry, 0)

        entries[0].set_dirty()
        self.assertCallbackCalled(entries[0], 1)
        self.assertCallbackCalled(entries[1], 0)
        self.assertCallbackCalled(entries[2], 0)
        self.assertCallbackCalled(entries[3], 0)
        self.assertCallbackCalled(entries[4], 0)

        entries[0].set_dirty()
        self.assertCallbackCalled(entries[0], 1)
        self.assertCallbackCalled(entries[1], 0)
        self.assertCallbackCalled(entries[2], 0)
        self.assertCallbackCalled(entries[3], 0)
        self.assertCallbackCalled(entries[4], 0)

        entries[0].set_dirty(False)
        entries[0].set_dirty()
        self.assertCallbackCalled(entries[0], 2)
        self.assertCallbackCalled(entries[1], 0)
        self.assertCallbackCalled(entries[2], 0)
        self.assertCallbackCalled(entries[3], 0)
        self.assertCallbackCalled(entries[4], 0)

        entries[2].set_dirty()
        self.assertCallbackCalled(entries[0], 2)
        self.assertCallbackCalled(entries[1], 0)
        self.assertCallbackCalled(entries[2], 1)
        self.assertCallbackCalled(entries[3], 0)
        self.assertCallbackCalled(entries[4], 0)

        # Add a second callback on entry 3. Should make 2 call on dirty
        ds.start_watching(entries[3].get_id(), self.entry_callback, dict(someParam=entries[3].get_id()))
        entries[3].set_dirty()
        self.assertCallbackCalled(entries[0], 2)
        self.assertCallbackCalled(entries[1], 0)
        self.assertCallbackCalled(entries[2], 1)
        self.assertCallbackCalled(entries[3], 2)
        self.assertCallbackCalled(entries[4], 0)

