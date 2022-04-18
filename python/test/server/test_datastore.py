#    test_datastore.py
#        Test the Datastore behaviour
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import unittest

from scrutiny.server.datastore import Datastore, DatastoreEntry


class TestDataStore(unittest.TestCase):
    def setUp(self):
        self.callback_call_history = {}

    def make_dummy_entries(self, n):
        for i in range(n):
            entry = DatastoreEntry(DatastoreEntry.Type.eVar, 'path_%d' % i)
            yield entry

    def entry_callback(self, owner, args, entry):
        if owner not in self.callback_call_history:
            self.callback_call_history[owner] = {}

        if entry.get_id() not in self.callback_call_history[owner]:
            self.callback_call_history[owner][entry.get_id()] = 0

        self.callback_call_history[owner][entry.get_id()] += 1

    def assertCallbackCalled(self, entry_id, owner, n, msg=None):
        if isinstance(entry_id, DatastoreEntry):
            entry_id = entry_id.get_id()

        if owner not in self.callback_call_history:
            count = 0
        else:
            if entry_id not in self.callback_call_history[owner]:
                count = 0
            else:
                count = self.callback_call_history[owner][entry_id]
        self.assertEqual(count, n, msg)

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

    # Make sure all callbacks are called when entry gets dirty
    def test_callback_on_value_change(self):
        entries = list(self.make_dummy_entries(5))
        ds = Datastore()
        ds.add_entries_quiet(entries)
        owner = 1234
        owner2 = 4567
        for entry in entries:
            ds.start_watching(entry.get_id(), callback_owner=owner, callback=self.entry_callback, args=dict(someParam=entry.get_id()))

        for entry in entries:
            self.assertCallbackCalled(entry, owner, 0)

        entries[0].execute_value_change_callback()
        self.assertCallbackCalled(entries[0], owner, 1)
        self.assertCallbackCalled(entries[1], owner, 0)
        self.assertCallbackCalled(entries[2], owner, 0)
        self.assertCallbackCalled(entries[3], owner, 0)
        self.assertCallbackCalled(entries[4], owner, 0)

        entries[0].execute_value_change_callback()
        self.assertCallbackCalled(entries[0], owner, 2)
        self.assertCallbackCalled(entries[1], owner, 0)
        self.assertCallbackCalled(entries[2], owner, 0)
        self.assertCallbackCalled(entries[3], owner, 0)
        self.assertCallbackCalled(entries[4], owner, 0)

        entries[2].execute_value_change_callback()
        self.assertCallbackCalled(entries[0], owner, 2)
        self.assertCallbackCalled(entries[1], owner, 0)
        self.assertCallbackCalled(entries[2], owner, 1)
        self.assertCallbackCalled(entries[3], owner, 0)
        self.assertCallbackCalled(entries[4], owner, 0)

        # Add a second callback on entry 3 with same owner. Should make 1 call on dirty, not 2
        ds.start_watching(entries[3].get_id(), callback_owner=owner, callback=self.entry_callback, args=dict(someParam=entry.get_id()))
        entries[3].execute_value_change_callback()
        self.assertCallbackCalled(entries[0], owner, 2)
        self.assertCallbackCalled(entries[1], owner, 0)
        self.assertCallbackCalled(entries[2], owner, 1)
        self.assertCallbackCalled(entries[3], owner, 1)
        self.assertCallbackCalled(entries[4], owner, 0)

        # Add a 2 callbacks with different owner. Should make 2 calls
        ds.start_watching(entries[4].get_id(), callback_owner=owner, callback=self.entry_callback, args=dict(someParam=entry.get_id()))
        ds.start_watching(entries[4].get_id(), callback_owner=owner2, callback=self.entry_callback, args=dict(someParam=entry.get_id()))
        entries[4].execute_value_change_callback()
        self.assertCallbackCalled(entries[0], owner, 2)
        self.assertCallbackCalled(entries[1], owner, 0)
        self.assertCallbackCalled(entries[2], owner, 1)
        self.assertCallbackCalled(entries[3], owner, 1)
        self.assertCallbackCalled(entries[4], owner, 1)
        self.assertCallbackCalled(entries[4], owner2, 1)
