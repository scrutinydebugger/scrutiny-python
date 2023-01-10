#    test_datastore.py
#        Test the Datastore behaviour
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

from scrutiny.server.datastore.datastore import Datastore
from scrutiny.server.datastore.entry_type import EntryType
from scrutiny.server.datastore.datastore_entry import *
from scrutiny.core.alias import Alias
from scrutiny.core.variable import *
from scrutiny.core.basic_types import *
from test import ScrutinyUnitTest

dummy_callback = lambda *args, **kwargs: None


class TestDataStore(ScrutinyUnitTest):
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
                entry = DatastoreAliasEntry(Alias(name, target='none'), refentry=entry_temp)
            else:
                dummy_rpv = RuntimePublishedValue(id=i, datatype=EmbeddedDataType.float32)
                entry = DatastoreRPVEntry(name, rpv=dummy_rpv)

            yield entry

    def value_change_callback(self, owner: str, entry: DatastoreEntry):
        if owner not in self.value_change_callback_call_history:
            self.value_change_callback_call_history[owner] = {}

        if entry.get_id() not in self.value_change_callback_call_history[owner]:
            self.value_change_callback_call_history[owner][entry.get_id()] = 0

        self.value_change_callback_call_history[owner][entry.get_id()] += 1

    def target_update_callback(self, success: bool, entry: DatastoreEntry, timestamp: float):

        if entry.get_id() not in self.target_update_callback_call_history:
            self.target_update_callback_call_history[entry.get_id()] = 0

        self.target_update_callback_call_history[entry.get_id()] += 1

    def clear_callback_count(self):
        self.value_change_callback_call_history = {}
        self.target_update_callback_call_history = {}

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

    def assertTargetUpdateCallbackCalled(self, entry_id, n, msg=None):
        if isinstance(entry_id, DatastoreEntry):
            entry_id = entry_id.get_id()

        if entry_id not in self.target_update_callback_call_history:
            count = 0
        else:
            count = self.target_update_callback_call_history[entry_id]
        self.assertEqual(count, n, msg)

    def test_add_get(self):
        ds = Datastore()
        entries = []
        entries += list(self.make_dummy_entries(4, EntryType.Var))
        entries += [DatastoreAliasEntry(Alias('alias_1', target='none'), refentry=entries[0]),
                    DatastoreAliasEntry(Alias('alias_2', target='none'), refentry=entries[1])]
        entries += list(self.make_dummy_entries(5, EntryType.RuntimePublishedValue))

        for entry in entries:
            ds.add_entry(entry)

        self.assertEqual(ds.get_entries_count(), 4 + 2 + 5)
        self.assertEqual(ds.get_entries_count(EntryType.Var), 4)
        self.assertEqual(ds.get_entries_count(EntryType.Alias), 2)
        self.assertEqual(ds.get_entries_count(EntryType.RuntimePublishedValue), 5)

        ds_entries = list(ds.get_all_entries())
        self.assertEqual(len(ds_entries), 4 + 2 + 5)
        for entry in ds_entries:
            self.assertIn(entry, entries)

        ds_entries = list(ds.get_entries_list_by_type(EntryType.Var))
        self.assertEqual(len(ds_entries), 4)
        for entry in ds_entries:
            self.assertEqual(entry.get_type(), EntryType.Var)
            self.assertIn(entry, entries)

        ds_entries = list(ds.get_entries_list_by_type(EntryType.Alias))
        self.assertEqual(len(ds_entries), 2)
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

        for entry_type in [EntryType.Var, EntryType.RuntimePublishedValue]:
            entries = list(self.make_dummy_entries(5, entry_type))

            ds = Datastore()
            ds.add_entries(entries)
            owner = 'watcher1'
            owner2 = 'watcher2'
            for entry in entries:
                ds.start_watching(entry.get_id(), watcher=owner, value_change_callback=self.value_change_callback)

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
            ds.start_watching(entries[3].get_id(), watcher=owner, value_change_callback=self.value_change_callback)
            entries[3].set_value(3)
            self.assertValueChangeCallbackCalled(entries[0], owner, 2, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[1], owner, 0, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[2], owner, 1, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[3], owner, 1, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[4], owner, 0, "EntryType=%s" % entry_type)

            # Add a 2 callbacks with different owner. Should make 2 calls
            ds.start_watching(entries[4].get_id(), watcher=owner, value_change_callback=self.value_change_callback)
            ds.start_watching(entries[4].get_id(), watcher=owner2,
                              value_change_callback=self.value_change_callback)
            entries[4].set_value(4)
            self.assertValueChangeCallbackCalled(entries[0], owner, 2, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[1], owner, 0, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[2], owner, 1, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[3], owner, 1, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[4], owner, 1, "EntryType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[4], owner2, 1, "EntryType=%s" % entry_type)

    # Make sure all callbacks are called when entry gets dirty
    def test_callback_on_target_update(self):
        for entry_type in [EntryType.RuntimePublishedValue, EntryType.Var]:
            entries = list(self.make_dummy_entries(5, entry_type))

            ds = Datastore()
            ds.add_entries(entries)
            owner = 'watcher1'
            owner2 = 'watcher2'
            for entry in entries:
                ds.start_watching(entry.get_id(), watcher=owner)

            for entry in entries:
                self.assertTargetUpdateCallbackCalled(entry, 0)

            self.assertFalse(entries[0].has_pending_target_update())
            self.assertIsNone(entries[0].pop_target_update_request())
            entries[0].update_target_value(123, callback=self.target_update_callback)
            self.assertTrue(entries[0].has_pending_target_update())
            update_request = entries[0].pop_target_update_request()
            self.assertEqual(update_request.get_value(), 123)
            self.assertIsNotNone(update_request)
            update_request.complete(success=True)

            self.assertTargetUpdateCallbackCalled(entries[0], 1, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[1], 0, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[2], 0, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[3], 0, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[4], 0, "EntryType=%s" % entry_type)

            entries[0].update_target_value(1, callback=self.target_update_callback)
            entries[0].pop_target_update_request().complete(success=True)
            self.assertTargetUpdateCallbackCalled(entries[0], 2, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[1], 0, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[2], 0, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[3], 0, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[4], 0, "EntryType=%s" % entry_type)

            entries[2].update_target_value(2, callback=self.target_update_callback)
            entries[2].pop_target_update_request().complete(success=True)
            self.assertTargetUpdateCallbackCalled(entries[0], 2, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[1], 0, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[2], 1, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[3], 0, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[4], 0, "EntryType=%s" % entry_type)

            # Add a second callback on entry 3 with same owner. Should make 1 call on dirty, not 2
            ds.start_watching(entries[3].get_id(), watcher=owner)
            entries[3].update_target_value(3, callback=self.target_update_callback)
            entries[3].pop_target_update_request().complete(success=True)
            self.assertTargetUpdateCallbackCalled(entries[0], 2, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[1], 0, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[2], 1, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[3], 1, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[4], 0, "EntryType=%s" % entry_type)

            # Add a 2 callbacks with different owner. Should make 2 calls
            ds.start_watching(entries[4].get_id(), watcher=owner, target_update_callback=self.target_update_callback)
            ds.start_watching(entries[4].get_id(), watcher=owner2, target_update_callback=self.target_update_callback)
            entries[4].update_target_value(4, callback=self.target_update_callback)
            entries[4].pop_target_update_request().complete(success=False)
            self.assertTargetUpdateCallbackCalled(entries[0], 2, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[1], 0, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[2], 1, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[3], 1, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[4], 1, "EntryType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[4], 1, "EntryType=%s" % entry_type)

    # Make sure we manage correctly multiple watchers
    def test_watch_behavior(self):
        for entry_type in [EntryType.Var, EntryType.RuntimePublishedValue]:
            entries = list(self.make_dummy_entries(4, entry_type))
            ds = Datastore()
            ds.add_entries(entries)

            for entry in entries:
                self.assertFalse(ds.is_watching(entry, 'watcher1'))
                self.assertFalse(ds.is_watching(entry, 'watcher2'))

                ds.start_watching(entry, watcher='watcher1', value_change_callback=lambda: None)
                self.assertTrue(ds.is_watching(entry, 'watcher1'))
                self.assertFalse(ds.is_watching(entry, 'watcher2'))

                ds.start_watching(entry, watcher='watcher2', value_change_callback=lambda: None)
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

            for entry in entries:
                ds.start_watching(entry, watcher='watcher1', value_change_callback=lambda: None)
                ds.start_watching(entry, watcher='watcher2', value_change_callback=lambda: None)

            ds.stop_watching_all('watcher2')
            for entry in entries:
                self.assertTrue(ds.is_watching(entry, 'watcher1'))
                self.assertFalse(ds.is_watching(entry, 'watcher2'))

    def test_alias_behavior(self):
        var_entries = list(self.make_dummy_entries(4, EntryType.Var))
        rpv_entries = list(self.make_dummy_entries(4, EntryType.RuntimePublishedValue))

        alias_var_2 = DatastoreAliasEntry(Alias('alias_var_2', target='none'), refentry=var_entries[2])
        alias_var_2_2 = DatastoreAliasEntry(Alias('alias_var_2', target='none'), refentry=var_entries[2])
        alias_rpv_1 = DatastoreAliasEntry(Alias('alias_rpv_1', target='none'), refentry=rpv_entries[1])
        alias_rpv_1_2 = DatastoreAliasEntry(Alias('alias_rpv_1', target='none'), refentry=rpv_entries[1])

        ds = Datastore()
        ds.add_entries(var_entries)
        ds.add_entries(rpv_entries)

        ds.add_entry(alias_var_2)
        ds.add_entry(alias_var_2_2)
        ds.add_entry(alias_rpv_1)
        ds.add_entry(alias_rpv_1_2)

        watcher = 'potato'

        ds.start_watching(
            alias_var_2.get_id(),
            watcher=watcher,
            value_change_callback=self.value_change_callback
        )

        ds.start_watching(
            alias_var_2_2.get_id(),
            watcher=watcher,
            value_change_callback=self.value_change_callback
        )

        ds.start_watching(
            alias_rpv_1.get_id(),
            watcher=watcher,
            value_change_callback=self.value_change_callback
        )

        ds.start_watching(
            alias_rpv_1_2.get_id(),
            watcher=watcher,
            value_change_callback=self.value_change_callback
        )

        ds.set_value(var_entries[2], 55)
        self.assertEqual(var_entries[2].get_value(), 55)
        self.assertEqual(alias_var_2.get_value(), 55)
        self.assertEqual(alias_var_2_2.get_value(), 55)

        self.assertValueChangeCallbackCalled(var_entries[2].get_id(), watcher, n=0)  # Not watching this one, so n=0
        self.assertValueChangeCallbackCalled(alias_var_2.get_id(), watcher, n=1)
        self.assertValueChangeCallbackCalled(alias_var_2_2.get_id(), watcher, n=1)

        ds.update_target_value(alias_rpv_1, 123, self.target_update_callback)
        self.assertTrue(rpv_entries[1].has_pending_target_update())
        update_request = rpv_entries[1].pop_target_update_request()
        self.assertEqual(update_request.get_value(), 123)
        update_request.complete(success=True)

        self.assertTargetUpdateCallbackCalled(rpv_entries[1], n=0)
        self.assertTargetUpdateCallbackCalled(alias_rpv_1, n=1)
        self.assertTargetUpdateCallbackCalled(alias_rpv_1_2, n=0)

        ds.update_target_value(alias_rpv_1_2, 321, self.target_update_callback)
        self.assertTrue(rpv_entries[1].has_pending_target_update())
        update_request = rpv_entries[1].pop_target_update_request()
        self.assertEqual(update_request.get_value(), 321)
        update_request.complete(success=False)

        self.assertTargetUpdateCallbackCalled(rpv_entries[1], n=0)
        self.assertTargetUpdateCallbackCalled(alias_rpv_1, n=1)
        self.assertTargetUpdateCallbackCalled(alias_rpv_1_2, n=1)
