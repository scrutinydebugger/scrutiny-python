#    test_datastore.py
#        Test the Datastore behavior
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny.server.datastore.datastore import Datastore
from scrutiny.server.datastore.datastore_entry import *
from scrutiny.core.alias import Alias
from scrutiny.core.variable import *
from scrutiny.core.embedded_enum import EmbeddedEnum
from scrutiny.core.basic_types import *
from test import ScrutinyUnitTest
from typing import Dict, Optional

dummy_callback = lambda *args, **kwargs: None


class TestDataStore(ScrutinyUnitTest):
    def setUp(self):
        self.value_change_callback_call_history = {}
        self.target_update_callback_call_history = {}

    def make_dummy_entries(self, n: int, entry_type: WatchableType, prefix='path'):
        dummy_var = Variable('dummy', 
            vartype=EmbeddedDataType.float32, 
            path_segments=['a', 'b', 'c'], 
            location=0x12345678, 
            endianness=Endianness.Little
        )
        
        for i in range(n):
            name = '%s_%d' % (prefix, i)
            entry: DatastoreEntry
            if entry_type == WatchableType.Variable:
                entry = DatastoreVariableEntry(name, variable_def=dummy_var)
            elif entry_type == WatchableType.Alias:
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
        entries += list(self.make_dummy_entries(4, WatchableType.Variable))
        entries += [DatastoreAliasEntry(Alias('alias_1', target='none'), refentry=entries[0]),
                    DatastoreAliasEntry(Alias('alias_2', target='none'), refentry=entries[1])]
        entries += list(self.make_dummy_entries(5, WatchableType.RuntimePublishedValue))

        for entry in entries:
            ds.add_entry(entry)

        self.assertEqual(ds.get_entries_count(), 4 + 2 + 5)
        self.assertEqual(ds.get_entries_count(WatchableType.Variable), 4)
        self.assertEqual(ds.get_entries_count(WatchableType.Alias), 2)
        self.assertEqual(ds.get_entries_count(WatchableType.RuntimePublishedValue), 5)

        ds_entries = list(ds.get_all_entries())
        self.assertEqual(len(ds_entries), 4 + 2 + 5)
        for entry in ds_entries:
            self.assertIn(entry, entries)

        ds_entries = list(ds.get_all_entries(WatchableType.Variable))
        self.assertEqual(len(ds_entries), 4)
        for entry in ds_entries:
            self.assertEqual(entry.get_type(), WatchableType.Variable)
            self.assertIn(entry, entries)

        ds_entries = list(ds.get_all_entries(WatchableType.Alias))
        self.assertEqual(len(ds_entries), 2)
        for entry in ds_entries:
            self.assertEqual(entry.get_type(), WatchableType.Alias)
            self.assertIn(entry, entries)

        ds_entries = list(ds.get_all_entries(WatchableType.RuntimePublishedValue))
        self.assertEqual(len(ds_entries), 5)
        for entry in ds_entries:
            self.assertEqual(entry.get_type(), WatchableType.RuntimePublishedValue)
            self.assertIn(entry, entries)

    def test_entry_no_duplicate_id(self):
        n = 10000
        entries = list(self.make_dummy_entries(n, WatchableType.Variable))
        entries += list(self.make_dummy_entries(n, WatchableType.Alias))
        entries += list(self.make_dummy_entries(n, WatchableType.RuntimePublishedValue
                                                ))
        entry_ids = set()
        for entry in entries:
            self.assertNotIn(entry.get_id(), entry_ids)
            entry_ids.add(entry.get_id())

    # Make sure all callbacks are called when entry gets dirty
    def test_callback_on_value_change(self):

        for entry_type in [WatchableType.Variable, WatchableType.RuntimePublishedValue]:
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
            self.assertValueChangeCallbackCalled(entries[0], owner, 1, "WatchableType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[1], owner, 0, "WatchableType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[2], owner, 0, "WatchableType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[3], owner, 0, "WatchableType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[4], owner, 0, "WatchableType=%s" % entry_type)

            entries[0].set_value(1)
            self.assertValueChangeCallbackCalled(entries[0], owner, 2, "WatchableType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[1], owner, 0, "WatchableType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[2], owner, 0, "WatchableType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[3], owner, 0, "WatchableType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[4], owner, 0, "WatchableType=%s" % entry_type)

            entries[2].set_value(2)
            self.assertValueChangeCallbackCalled(entries[0], owner, 2, "WatchableType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[1], owner, 0, "WatchableType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[2], owner, 1, "WatchableType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[3], owner, 0, "WatchableType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[4], owner, 0, "WatchableType=%s" % entry_type)

            # Add a second callback on entry 3 with same owner. Should make 1 call on dirty, not 2
            ds.start_watching(entries[3].get_id(), watcher=owner, value_change_callback=self.value_change_callback)
            entries[3].set_value(3)
            self.assertValueChangeCallbackCalled(entries[0], owner, 2, "WatchableType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[1], owner, 0, "WatchableType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[2], owner, 1, "WatchableType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[3], owner, 1, "WatchableType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[4], owner, 0, "WatchableType=%s" % entry_type)

            # Add a 2 callbacks with different owner. Should make 2 calls
            ds.start_watching(entries[4].get_id(), watcher=owner, value_change_callback=self.value_change_callback)
            ds.start_watching(entries[4].get_id(), watcher=owner2,
                              value_change_callback=self.value_change_callback)
            entries[4].set_value(4)
            self.assertValueChangeCallbackCalled(entries[0], owner, 2, "WatchableType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[1], owner, 0, "WatchableType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[2], owner, 1, "WatchableType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[3], owner, 1, "WatchableType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[4], owner, 1, "WatchableType=%s" % entry_type)
            self.assertValueChangeCallbackCalled(entries[4], owner2, 1, "WatchableType=%s" % entry_type)

    # Make sure all callbacks are called when entry gets dirty
    def test_callback_on_target_update(self):
        for entry_type in [WatchableType.RuntimePublishedValue, WatchableType.Variable]:
            entries = list(self.make_dummy_entries(5, entry_type))

            ds = Datastore()
            ds.add_entries(entries)
            owner = 'watcher1'
            owner2 = 'watcher2'
            for entry in entries:
                ds.start_watching(entry.get_id(), watcher=owner)

            for entry in entries:
                self.assertTargetUpdateCallbackCalled(entry, 0)

            self.assertIsNone(ds.pop_target_update_request())
            ds.update_target_value(entries[0], 123, callback=self.target_update_callback)
            update_request = ds.pop_target_update_request()
            self.assertEqual(update_request.get_value(), 123)
            self.assertIsNotNone(update_request)
            update_request.complete(success=True)

            self.assertTargetUpdateCallbackCalled(entries[0], 1, "WatchableType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[1], 0, "WatchableType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[2], 0, "WatchableType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[3], 0, "WatchableType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[4], 0, "WatchableType=%s" % entry_type)

            ds.update_target_value(entries[0], 1, callback=self.target_update_callback)
            ds.pop_target_update_request().complete(success=True)
            self.assertTargetUpdateCallbackCalled(entries[0], 2, "WatchableType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[1], 0, "WatchableType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[2], 0, "WatchableType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[3], 0, "WatchableType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[4], 0, "WatchableType=%s" % entry_type)

            ds.update_target_value(entries[2], 2, callback=self.target_update_callback)
            ds.pop_target_update_request().complete(success=True)
            self.assertTargetUpdateCallbackCalled(entries[0], 2, "WatchableType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[1], 0, "WatchableType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[2], 1, "WatchableType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[3], 0, "WatchableType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[4], 0, "WatchableType=%s" % entry_type)

            # Add a second callback on entry 3 with same owner. Should make 1 call on dirty, not 2
            ds.start_watching(entries[3].get_id(), watcher=owner)
            ds.update_target_value(entries[3], 3, callback=self.target_update_callback)
            ds.pop_target_update_request().complete(success=True)
            self.assertTargetUpdateCallbackCalled(entries[0], 2, "WatchableType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[1], 0, "WatchableType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[2], 1, "WatchableType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[3], 1, "WatchableType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[4], 0, "WatchableType=%s" % entry_type)

            # Add a 2 callbacks with different owner. Should make 2 calls
            ds.start_watching(entries[4].get_id(), watcher=owner, target_update_callback=self.target_update_callback)
            ds.start_watching(entries[4].get_id(), watcher=owner2, target_update_callback=self.target_update_callback)
            ds.update_target_value(entries[4], 4, callback=self.target_update_callback)
            ds.pop_target_update_request().complete(success=False)
            self.assertTargetUpdateCallbackCalled(entries[0], 2, "WatchableType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[1], 0, "WatchableType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[2], 1, "WatchableType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[3], 1, "WatchableType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[4], 1, "WatchableType=%s" % entry_type)
            self.assertTargetUpdateCallbackCalled(entries[4], 1, "WatchableType=%s" % entry_type)

    # Make sure we manage correctly multiple watchers
    def test_watch_behavior(self):
        for entry_type in [WatchableType.Variable, WatchableType.RuntimePublishedValue]:
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
        var_entries = list(self.make_dummy_entries(4, WatchableType.Variable))
        rpv_entries = list(self.make_dummy_entries(4, WatchableType.RuntimePublishedValue))

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
        update_request = ds.pop_target_update_request()
        self.assertEqual(update_request.get_value(), 123)
        update_request.complete(success=True)

        self.assertTargetUpdateCallbackCalled(rpv_entries[1], n=0)
        self.assertTargetUpdateCallbackCalled(alias_rpv_1, n=1)
        self.assertTargetUpdateCallbackCalled(alias_rpv_1_2, n=0)

        ds.update_target_value(alias_rpv_1_2, 321, self.target_update_callback)
        update_request = ds.pop_target_update_request()
        self.assertEqual(update_request.get_value(), 321)
        update_request.complete(success=False)

        self.assertTargetUpdateCallbackCalled(rpv_entries[1], n=0)
        self.assertTargetUpdateCallbackCalled(alias_rpv_1, n=1)
        self.assertTargetUpdateCallbackCalled(alias_rpv_1_2, n=1)

    def test_enum_access(self):
        var1 = Variable('var1', 
            vartype=EmbeddedDataType.uint32, 
            path_segments=['a', 'b', 'c'], 
            location=0x12345678, 
            endianness=Endianness.Little,
            enum=EmbeddedEnum('var1_enum', vals={'a':1, 'b':2, 'c':3})
        )


        var1_entry = DatastoreVariableEntry('/a/b/c/var1', var1)
        rpv1_entry = DatastoreRPVEntry('/a/b/c/rpv1', RuntimePublishedValue(id=0x1234, datatype=EmbeddedDataType.uint16))

        alias_var_1_no_enum = DatastoreAliasEntry(
            aliasdef=Alias('alias_var_1_no_enum', target='/a/b/c/var1'), 
            refentry=var1_entry
        )

        alias_var_1_enum = DatastoreAliasEntry(
            aliasdef=Alias('alias_var_1_enum', 
                target='/a/b/c/var1',
                enum=EmbeddedEnum(
                    name='alias_var1_enum',
                    vals={'aaa':111, 'bbb':222, 'ccc':333}
                ),
            ), 
            refentry=var1_entry
        )

        alias_rpv_entry_enum = DatastoreAliasEntry(
            aliasdef=Alias('alias_rpv_entry_enum', 
                target='/a/b/c/rpv1',
                enum=EmbeddedEnum(
                    name='alias_rpv_enum',
                    vals={'xxx':1, 'yyy':2, 'zzz':3}
                ),
            ), 
            refentry=rpv1_entry
        )
    
        self.assertTrue(var1_entry.has_enum()) 
        self.assertFalse(rpv1_entry.has_enum())
        self.assertTrue(alias_var_1_no_enum.has_enum()) # Defaults to the variable enum
        self.assertTrue(alias_var_1_enum.has_enum())
        self.assertTrue(alias_rpv_entry_enum.has_enum())

        self.assertEqual(var1_entry.get_enum().name, 'var1_enum')
        self.assertEqual(alias_var_1_no_enum.get_enum().name, 'var1_enum')
        self.assertEqual(alias_var_1_enum.get_enum().name, 'alias_var1_enum')
        self.assertEqual(alias_rpv_entry_enum.get_enum().name, 'alias_rpv_enum')


if __name__ == '__main__':
    import unittest
    unittest.main()
