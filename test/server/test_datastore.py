#    test_datastore.py
#        Test the Datastore behaviour
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import unittest

from scrutiny.server.datastore import *
from scrutiny.core.variable import *
from scrutiny.core.basic_types import *


dummy_callback = lambda *args, **kwargs: None


class TestDataStore(unittest.TestCase):
    def setUp(self):
        self.value_change_callback_call_history = {}
        self.target_update_callback_call_history = {}

    def make_dummy_entries(self, n: int, entry_type: EntryType, prefix='path'):
        dummy_var = Variable('dummy', vartype=EmbeddedDataType.float32, path_segments=[
                             'a', 'b', 'c'], location=0x12345678, endianness=Endianness.Little)
        for i in range(n):
            name = '%s_%d' % (prefix, i)
            if entry_type == EntryType.Var:
                entry = DatastoreVariableEntry(name, variable_def=dummy_var)
            elif entry_type == EntryType.Alias:
                entry_temp = DatastoreVariableEntry(name, variable_def=dummy_var)
                entry = DatastoreAliasEntry(name, refentry=entry_temp)
            else:
                dummy_rpv = RuntimePublishedValue(id=i, datatype=EmbeddedDataType.float32)
                entry = DatastoreRPVEntry(name, rpv=dummy_rpv)

            yield entry

    def value_change_callback(self, owner: str, args: Any, entry: DatastoreEntry):
        if owner not in self.value_change_callback_call_history:
            self.value_change_callback_call_history[owner] = {}

        if entry.get_id() not in self.value_change_callback_call_history[owner]:
            self.value_change_callback_call_history[owner][entry.get_id()] = 0

        self.value_change_callback_call_history[owner][entry.get_id()] += 1

    def target_update_callback(self, owner: str, args: Any, entry: DatastoreEntry):
        if owner not in self.target_update_callback_call_history:
            self.target_update_callback_call_history[owner] = {}

        if entry.get_id() not in self.target_update_callback_call_history[owner]:
            self.target_update_callback_call_history[owner][entry.get_id()] = 0

        self.target_update_callback_call_history[owner][entry.get_id()] += 1

    def assertValueChangeCallbackCalled(self, entry_id, owner, n, msg=None):
        if isinstance(entry_id, DatastoreEntry):
            entry_id = entry_id.get_id()

        if owner not in self.value_change_callback_call_history:
            count = 0
        else:
            if entry_id not in self.value_change_callback_call_history[owner]:
                count = 0
            else:
                count = self.value_change_callback_call_history[owner][entry_id]
        self.assertEqual(count, n, msg)

    def assertTargetUpdateCallbackCalled(self, entry_id, owner, n, msg=None):
        if isinstance(entry_id, DatastoreEntry):
            entry_id = entry_id.get_id()

        if owner not in self.target_update_callback_call_history:
            count = 0
        else:
            if entry_id not in self.target_update_callback_call_history[owner]:
                count = 0
            else:
                count = self.target_update_callback_call_history[owner][entry_id]
        self.assertEqual(count, n, msg)

    def test_add_get(self):
        ds = Datastore()
        entries = []
        entries += list(self.make_dummy_entries(3, EntryType.Var))
        entries += list(self.make_dummy_entries(4, EntryType.Alias))
        entries += list(self.make_dummy_entries(5, EntryType.RuntimePublishedValue))

        for entry in entries:
            ds.add_entry(entry)

        self.assertEqual(ds.get_entries_count(), 3 + 4 + 5)
        self.assertEqual(ds.get_entries_count(EntryType.Var), 3)
        self.assertEqual(ds.get_entries_count(EntryType.Alias), 4)
        self.assertEqual(ds.get_entries_count(EntryType.RuntimePublishedValue), 5)

        ds_entries = list(ds.get_all_entries())
        self.assertEqual(len(ds_entries), 3 + 4 + 5)
        for entry in ds_entries:
            self.assertIn(entry, entries)

        ds_entries = list(ds.get_entries_list_by_type(EntryType.Var))
        self.assertEqual(len(ds_entries), 3)
        for entry in ds_entries:
            self.assertEqual(entry.get_type(), EntryType.Var)
            self.assertIn(entry, entries)

        ds_entries = list(ds.get_entries_list_by_type(EntryType.Alias))
        self.assertEqual(len(ds_entries), 4)
        for entry in ds_entries:
            self.assertEqual(entry.get_type(), EntryType.Alias)
            self.assertIn(entry, entries)

        ds_entries = list(ds.get_entries_list_by_type(EntryType.RuntimePublishedValue))
        self.assertEqual(len(ds_entries), 5)
        for entry in ds_entries:
            self.assertEqual(entry.get_type(), EntryType.RuntimePublishedValue)
            self.assertIn(entry, entries)

    def test_entry_no_duplicate_id(self):
        n = 10000
        entries = list(self.make_dummy_entries(n, EntryType.Var))
        entries += list(self.make_dummy_entries(n, EntryType.Alias))
        entries += list(self.make_dummy_entries(n, EntryType.RuntimePublishedValue
                                                ))
        entry_ids = set()
        for entry in entries:
            self.assertNotIn(entry.get_id(), entry_ids)
            entry_ids.add(entry.get_id())

    # Make sure all callbacks are called when entry gets dirty
    def test_callback_on_value_change(self):

        for entry_type in EntryType:
            entries = list(self.make_dummy_entries(5, entry_type))

            ds = Datastore()
            ds.add_entries_quiet(entries)
            owner = 'watcher1'
            owner2 = 'watcher2'
            for entry in entries:
                ds.start_watching(entry.get_id(), watcher=owner, value_update_callback=self.value_change_callback,
                                  args=dict(someParam=entry.get_id()))

            for entry in entries:
                self.assertValueChangeCallbackCalled(entry, owner, 0)

            entries[0].set_value(0)
            self.assertValueChangeCallbackCalled(entries[0], owner, 1, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[1], owner, 0, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[2], owner, 0, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[3], owner, 0, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[4], owner, 0, "EntryType=%s" % entry_type)

            entries[0].set_value(1)
            self.assertValueChangeCallbackCalled(entries[0], owner, 2, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[1], owner, 0, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[2], owner, 0, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[3], owner, 0, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[4], owner, 0, "EntryType=%s" % entry_type)

            entries[2].set_value(2)
            self.assertValueChangeCallbackCalled(entries[0], owner, 2, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[1], owner, 0, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[2], owner, 1, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[3], owner, 0, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[4], owner, 0, "EntryType=%s" % entry_type)

            # Add a second callback on entry 3 with same owner. Should make 1 call on dirty, not 2
            ds.start_watching(entries[3].get_id(), watcher=owner, value_update_callback=self.value_change_callback,
                              args=dict(someParam=entry.get_id()))
            entries[3].set_value(3)
            self.assertValueChangeCallbackCalled(entries[0], owner, 2, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[1], owner, 0, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[2], owner, 1, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[3], owner, 1, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[4], owner, 0, "EntryType=%s" % entry_type)

            # Add a 2 callbacks with different owner. Should make 2 calls
            ds.start_watching(entries[4].get_id(), watcher=owner, value_update_callback=self.value_change_callback,
                              args=dict(someParam=entry.get_id()))
            ds.start_watching(entries[4].get_id(), watcher=owner2,
                              value_update_callback=self.value_change_callback, args=dict(someParam=entry.get_id()))
            entries[4].set_value(4)
            self.assertValueChangeCallbackCalled(entries[0], owner, 2, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[1], owner, 0, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[2], owner, 1, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[3], owner, 1, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[4], owner, 1, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[4], owner2, 1, "EntryType=%s" % entry_type)

    # Make sure all callbacks are called when entry gets dirty
    def test_callback_on_target_update(self):
        for entry_type in EntryType:
            entries = list(self.make_dummy_entries(5, entry_type))

            ds = Datastore()
            ds.add_entries_quiet(entries)
            owner = 'watcher1'
            owner2 = 'watcher2'
            for entry in entries:
                ds.start_watching(entry.get_id(), watcher=owner, target_update_callback=self.target_update_callback,
                                  args=dict(someParam=entry.get_id()))

            for entry in entries:
                self.assertTargetUpdateCallbackCalled(entry, owner, 0)

            entries[0].update_target_value(0)
            entries[0].mark_target_update_request_complete()
            self.assertTargetUpdateCallbackCalled(entries[0], owner, 1, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[1], owner, 0, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[2], owner, 0, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[3], owner, 0, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[4], owner, 0, "EntryType=%s" % entry_type)

            entries[0].update_target_value(1)
            entries[0].mark_target_update_request_complete()
            self.assertTargetUpdateCallbackCalled(entries[0], owner, 2, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[1], owner, 0, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[2], owner, 0, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[3], owner, 0, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[4], owner, 0, "EntryType=%s" % entry_type)

            entries[2].update_target_value(2)
            entries[2].mark_target_update_request_complete()
            self.assertTargetUpdateCallbackCalled(entries[0], owner, 2, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[1], owner, 0, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[2], owner, 1, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[3], owner, 0, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[4], owner, 0, "EntryType=%s" % entry_type)

            # Add a second callback on entry 3 with same owner. Should make 1 call on dirty, not 2
            ds.start_watching(entries[3].get_id(), watcher=owner, target_update_callback=self.target_update_callback,
                              args=dict(someParam=entry.get_id()))
            entries[3].update_target_value(3)
            entries[3].mark_target_update_request_complete()
            self.assertTargetUpdateCallbackCalled(entries[0], owner, 2, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[1], owner, 0, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[2], owner, 1, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[3], owner, 1, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[4], owner, 0, "EntryType=%s" % entry_type)

            # Add a 2 callbacks with different owner. Should make 2 calls
            ds.start_watching(entries[4].get_id(), watcher=owner, target_update_callback=self.target_update_callback,
                              args=dict(someParam=entry.get_id()))
            ds.start_watching(entries[4].get_id(), watcher=owner2,
                              target_update_callback=self.target_update_callback, args=dict(someParam=entry.get_id()))
            entries[4].update_target_value(4)
            entries[4].mark_target_update_request_failed()
            self.assertTargetUpdateCallbackCalled(entries[0], owner, 2, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[1], owner, 0, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[2], owner, 1, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[3], owner, 1, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[4], owner, 1, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[4], owner2, 1, "EntryType=%s" % entry_type)

    # Make sure we manage correctly multiple watchers
    def test_watch_behavior(self):
        for entry_type in EntryType:
            entries = list(self.make_dummy_entries(4, entry_type))
            ds = Datastore()
            ds.add_entries_quiet(entries)

            for entry in entries:
                self.assertFalse(ds.is_watching(entry, 'watcher1'))
                self.assertFalse(ds.is_watching(entry, 'watcher2'))

                ds.start_watching(entry, watcher='watcher1', value_update_callback=lambda: None, target_update_callback=lambda: None)
                self.assertTrue(ds.is_watching(entry, 'watcher1'))
                self.assertFalse(ds.is_watching(entry, 'watcher2'))

                ds.start_watching(entry, watcher='watcher2', value_update_callback=lambda: None, target_update_callback=lambda: None)
                self.assertTrue(ds.is_watching(entry, 'watcher1'))
                self.assertTrue(ds.is_watching(entry, 'watcher2'))

            watchers = ds.get_watchers(entries[0])
            self.assertEqual(sorted(watchers), ['watcher1', 'watcher2'])

            watched_entries_id = ds.get_watched_entries_id(entry_type)
            self.assertEqual(len(watched_entries_id), len(entries))
            for entry in entries:
                self.assertIn(entry.get_id(), watched_entries_id)

            for entry in entries:
                ds.stop_watching(entry, watcher='watcher2')

            watchers = ds.get_watchers(entries[0])
            self.assertEqual(len(watchers), 1)
            self.assertEqual(watchers[0], 'watcher1')

            watched_entries_id = ds.get_watched_entries_id(entry_type)
            self.assertEqual(len(watched_entries_id), len(entries))
            for entry in entries:
                self.assertIn(entry.get_id(), watched_entries_id)

            ds.stop_watching(entries[0], watcher='watcher1')
            ds.stop_watching(entries[1], watcher='watcher1')

            watchers = ds.get_watchers(entries[0])
            self.assertEqual(len(watchers), 0)

            watched_entries_id = ds.get_watched_entries_id(entry_type)
            self.assertEqual(len(watched_entries_id), 2)
            self.assertIn(entries[2].get_id(), watched_entries_id)
            self.assertIn(entries[3].get_id(), watched_entries_id)

            ds.stop_watching(entries[2], watcher='watcher1')
            ds.stop_watching(entries[3], watcher='watcher1')

            watched_entries_id = ds.get_watched_entries_id(entry_type)
            self.assertEqual(len(watched_entries_id), 0)
