#    test_watchable_registry.py
#        A test suite for the WatchableRegistry object
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny import sdk
from scrutiny.core.basic_types import EmbeddedDataType
from scrutiny.core.embedded_enum import EmbeddedEnum
from scrutiny.gui.core.watchable_registry import (WatchableRegistry, WatchableRegistryError, 
                                                  WatchableRegistryNodeContent, ValueUpdate, WatcherNotFoundError, 
                                                  WatchableRegistryNodeNotFoundError)
from scrutiny.tools.thread_enforcer import ThreadEnforcer
from scrutiny.gui.core.threads import QT_THREAD_NAME

from test import ScrutinyUnitTest
from datetime import datetime
from typing import Optional

DUMMY_DATASET_RPV = {
    '/rpv/rpv1000' : sdk.WatchableConfiguration(server_id='rpv_111', watchable_type=sdk.WatchableType.RuntimePublishedValue, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/rpv/rpv1001' : sdk.WatchableConfiguration(server_id='rpv_222', watchable_type=sdk.WatchableType.RuntimePublishedValue, datatype=sdk.EmbeddedDataType.float32, enum=None)
}

DUMMY_DATASET_ALIAS = {
    '/alias/xxx/alias1' : sdk.WatchableConfiguration(server_id='alias_111', watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/alias/alias2' : sdk.WatchableConfiguration(server_id='alias_222', watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/alias/alias3' : sdk.WatchableConfiguration(server_id='alias_333', watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None)
}

DUMMY_DATASET_VAR = {
    '/var/xxx/var1' : sdk.WatchableConfiguration(server_id='var_111', watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/var/xxx/var2' : sdk.WatchableConfiguration(server_id='var_222', watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/var/var3' : sdk.WatchableConfiguration(server_id='var_333', watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/var/var4' : sdk.WatchableConfiguration(server_id='var_444', watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None)
}


All_DUMMY_DATA = {
    sdk.WatchableType.Variable: DUMMY_DATASET_VAR,
    sdk.WatchableType.Alias: DUMMY_DATASET_ALIAS,
    sdk.WatchableType.RuntimePublishedValue: DUMMY_DATASET_RPV,
}


class StubbedWatchableHandle:
    display_path:str
    configuration:sdk.WatchableConfiguration

    def __init__(self, display_path:str,
                watchable_type:sdk.WatchableType,
                datatype:EmbeddedDataType,
                enum:Optional[EmbeddedEnum],
                server_id:str
                 ) -> None:
        
        self.display_path = display_path
        self.configuration = sdk.WatchableConfiguration(
            watchable_type=watchable_type,
            datatype=datatype,
            enum=enum,
            server_id=server_id
        )

    @property
    def server_id(self):
        return self.configuration.server_id

class TestWatchableRegistry(ScrutinyUnitTest):
    def setUp(self) -> None:
        super().setUp()
        self.registry = WatchableRegistry()
        ThreadEnforcer.register_thread(QT_THREAD_NAME)

    def make_fake_watchable_from_registry(self, fqn:str) -> StubbedWatchableHandle:
        node = self.registry.read_fqn(fqn)
        return StubbedWatchableHandle(
            display_path=WatchableRegistry.FQN.parse(fqn).path,
            watchable_type=node.watchable_type,
            datatype=node.datatype,
            server_id=node.server_id,
            enum=node.enum
        )

    def test_ignore_empty_data(self):
        self.registry.write_content({
            sdk.WatchableType.Alias : DUMMY_DATASET_ALIAS,
            sdk.WatchableType.RuntimePublishedValue : {}  # Should be ignored
        })

        self.assertTrue(self.registry.has_data(sdk.WatchableType.Alias))
        self.assertFalse(self.registry.has_data(sdk.WatchableType.RuntimePublishedValue))
        self.assertFalse(self.registry.has_data(sdk.WatchableType.Variable))
    
    def test_fqn(self):
        for wt in sdk.WatchableType.get_valids():
            fqn = WatchableRegistry.FQN.make(wt, '/a/b/c')
            o = WatchableRegistry.FQN.parse(fqn)
            self.assertEqual(o.watchable_type, wt)
            self.assertEqual(o.path, '/a/b/c')
        
        with self.assertRaises(WatchableRegistryError):
            WatchableRegistry.FQN.parse('unknown:/a/b/c')
        
        with self.assertRaises(WatchableRegistryError):
            WatchableRegistry.FQN.parse('/a/b/c')

        self.assertEqual(WatchableRegistry.FQN.extend('var:/a/b/c', ['x', 'y']), 'var:/a/b/c/x/y')
        self.assertEqual(WatchableRegistry.FQN.extend('var:/a/b/c', 'x'), 'var:/a/b/c/x')
        self.assertEqual(WatchableRegistry.FQN.extend('var:', ['x', 'y']), 'var:x/y')

        self.assertTrue(WatchableRegistry.FQN.is_equal('var:/a/b/c', 'var:a/b//c/'))
        self.assertFalse(WatchableRegistry.FQN.is_equal('var:/a/b/c', 'alias:a/b//c/'))
        self.assertFalse(WatchableRegistry.FQN.is_equal('var:/a/b/c', 'alias:/a/b/c'))

        self.assertFalse(WatchableRegistry.FQN.is_equal('var:/a/b/c', 'var:/a/c'))
        self.assertFalse(WatchableRegistry.FQN.is_equal('var:/a/b/c', 'var:/a/b/d'))
        
    def test_internal_direct_add_get(self):
        obj1 = sdk.WatchableConfiguration(
             
            server_id="aaa",
            watchable_type=sdk.WatchableType.Alias,
            datatype=sdk.EmbeddedDataType.float32,
            enum=None
        )

        obj2 = sdk.WatchableConfiguration(
            server_id="bbb",
            watchable_type=sdk.WatchableType.Variable,
            datatype=sdk.EmbeddedDataType.float32,
            enum=None
        )
        
        self.registry._add_watchable('/a/b/c', obj1)
        self.registry._add_watchable('/a/b/d/e', obj2)   # type is optional when setting

        o1 = self.registry.read(sdk.WatchableType.Alias, '/a/b/c')
        self.assertIs(o1, obj1)
        with self.assertRaises(WatchableRegistryError):
            self.registry.read(sdk.WatchableType.Variable, '/a/b/c')
        
        o2 = self.registry.read_fqn('var:/a/b/d/e')
        self.assertIs(obj2, o2)

    def test_root_not_writable(self):
        obj1 = sdk.WatchableConfiguration(
            server_id="aaa",
            watchable_type=sdk.WatchableType.Alias,
            datatype=sdk.EmbeddedDataType.float32,
            enum=None
        )

        with self.assertRaises(WatchableRegistryError):
            self.registry._add_watchable( '/', obj1)

    def test_query_node_type(self):
        self.registry.write_content(All_DUMMY_DATA)

        self.assertTrue(self.registry.get_watchable_count(sdk.WatchableType.Variable), len(DUMMY_DATASET_VAR))
        self.assertTrue(self.registry.get_watchable_count(sdk.WatchableType.Alias), len(DUMMY_DATASET_ALIAS))
        self.assertTrue(self.registry.get_watchable_count(sdk.WatchableType.RuntimePublishedValue), len(DUMMY_DATASET_RPV))

        self.assertTrue(self.registry.is_watchable_fqn('alias:/alias/xxx/alias1'))
        self.assertFalse(self.registry.is_watchable_fqn('alias:/alias/xxx'))
        self.assertFalse(self.registry.is_watchable_fqn('alias:Idontexist'))
    
    def test_cannot_overwrite_without_clear(self):
        obj1 = sdk.WatchableConfiguration(
            server_id="aaa",
            watchable_type=sdk.WatchableType.Variable,
            datatype=sdk.EmbeddedDataType.float32,
            enum=None
        )

        obj2 = sdk.WatchableConfiguration(
            server_id="bbb",
            watchable_type=sdk.WatchableType.Variable,
            datatype=sdk.EmbeddedDataType.float32,
            enum=None
        )

        self.registry._add_watchable('/aaa/bbb', obj1)
        with self.assertRaises(WatchableRegistryError):
            self.registry._add_watchable('/aaa/bbb', obj2)

    def test_can_have_same_path_if_different_type(self):
        obj1 = sdk.WatchableConfiguration(
            server_id="aaa",
            watchable_type=sdk.WatchableType.Alias,
            datatype=sdk.EmbeddedDataType.float32,
            enum=None
        )

        obj2 = sdk.WatchableConfiguration(
            server_id="bbb",
            watchable_type=sdk.WatchableType.Variable,
            datatype=sdk.EmbeddedDataType.float32,
            enum=None
        )

        self.registry._add_watchable('/aaa/bbb', obj1)
        self.registry._add_watchable('/aaa/bbb', obj2)
        
    def test_read_write(self):
        for path, desc in DUMMY_DATASET_VAR.items():
            self.registry._add_watchable(path, desc)
        for path, desc in DUMMY_DATASET_ALIAS.items():
            self.registry._add_watchable(path, desc)
        for path, desc in DUMMY_DATASET_RPV.items():
            self.registry._add_watchable(path, desc)
        

        node = self.registry.read_fqn('var:/')
        assert isinstance(node, WatchableRegistryNodeContent)
        self.assertEqual(len(node.watchables), 0)
        self.assertEqual(len(node.subtree), 1)

        self.assertIn('var', node.subtree)


        node = self.registry.read_fqn('var:/var')
        assert isinstance(node, WatchableRegistryNodeContent)
        self.assertEqual(len(node.watchables), 2)
        self.assertEqual(len(node.subtree), 1)

        self.assertIn('xxx', node.subtree)
        self.assertIn('var3', node.watchables)
        self.assertEqual(DUMMY_DATASET_VAR['/var/var3'], node.watchables['var3'])

        self.assertIn('var4', node.watchables)
        self.assertEqual(DUMMY_DATASET_VAR['/var/var4'], node.watchables['var4'])


        node = self.registry.read_fqn('var:/var/xxx')
        assert isinstance(node, WatchableRegistryNodeContent)
        self.assertEqual(len(node.watchables), 2)
        self.assertEqual(len(node.subtree), 0)

        self.assertIn('var1', node.watchables)
        self.assertEqual(DUMMY_DATASET_VAR['/var/xxx/var1'], node.watchables['var1'])
        self.assertIn('var2', node.watchables)
        self.assertEqual(DUMMY_DATASET_VAR['/var/xxx/var2'], node.watchables['var2'])

    def test_clear_by_type(self):
        self.registry.write_content(All_DUMMY_DATA)

        self.assertTrue(self.registry.has_data(sdk.WatchableType.Variable))
        self.assertTrue(self.registry.has_data(sdk.WatchableType.Alias))
        self.assertTrue(self.registry.has_data(sdk.WatchableType.RuntimePublishedValue))

        had_data = self.registry.clear_content_by_type(sdk.WatchableType.Variable)
        self.assertTrue(had_data)
        self.assertFalse(self.registry.has_data(sdk.WatchableType.Variable))
        self.assertTrue(self.registry.has_data(sdk.WatchableType.Alias))
        self.assertTrue(self.registry.has_data(sdk.WatchableType.RuntimePublishedValue))
        had_data = self.registry.clear_content_by_type(sdk.WatchableType.Variable)
        self.assertFalse(had_data) 

        had_data = self.registry.clear_content_by_type(sdk.WatchableType.Alias)
        self.assertTrue(had_data)
        self.assertFalse(self.registry.has_data(sdk.WatchableType.Variable))
        self.assertFalse(self.registry.has_data(sdk.WatchableType.Alias))
        self.assertTrue(self.registry.has_data(sdk.WatchableType.RuntimePublishedValue))
        had_data = self.registry.clear_content_by_type(sdk.WatchableType.Alias)
        self.assertFalse(had_data)  

        had_data = self.registry.clear_content_by_type(sdk.WatchableType.RuntimePublishedValue)
        self.assertTrue(had_data)
        self.assertFalse(self.registry.has_data(sdk.WatchableType.Variable))
        self.assertFalse(self.registry.has_data(sdk.WatchableType.Alias))
        self.assertFalse(self.registry.has_data(sdk.WatchableType.RuntimePublishedValue))
        had_data = self.registry.clear_content_by_type(sdk.WatchableType.RuntimePublishedValue)
        self.assertFalse(had_data)

        self.assertFalse(self.registry.clear())

    def test_clear(self):
        self.registry.write_content(All_DUMMY_DATA)  
        self.assertTrue(self.registry.has_data(sdk.WatchableType.Variable))
        self.assertTrue(self.registry.has_data(sdk.WatchableType.Alias))
        self.assertTrue(self.registry.has_data(sdk.WatchableType.RuntimePublishedValue))

        had_data = self.registry.clear()
        self.assertTrue(had_data)
        
        self.assertFalse(self.registry.has_data(sdk.WatchableType.Variable))
        self.assertFalse(self.registry.has_data(sdk.WatchableType.Alias))
        self.assertFalse(self.registry.has_data(sdk.WatchableType.RuntimePublishedValue))

        self.assertFalse(self.registry.clear())

    def test_watcher_broadcast_logic(self):
        self.registry.write_content(All_DUMMY_DATA) 

        callback_history = {
            'watcher1' : [],
            'watcher2' : [],
        }
        def watch_callback(watcher, value_list):
            callback_history[watcher].append(value_list)

        self.registry.register_watcher('watcher1', watch_callback)
        self.registry.register_watcher('watcher2', watch_callback)

        var1fqn = f'var:/var/xxx/var1'
        var2fqn = f'var:/var/xxx/var2'
       
        var1_sdk_handle = self.make_fake_watchable_from_registry(var1fqn)
        var2_sdk_handle = self.make_fake_watchable_from_registry(var2fqn)

        self.registry.watch('watcher1', sdk.WatchableType.Variable, '/var/xxx/var1')
        self.registry.watch_fqn('watcher2', var1fqn)
        self.registry.watch_fqn('watcher2', var2fqn)
        self.assertEqual(self.registry.watched_entries_count(), 2)
        with self.assertRaises(WatcherNotFoundError):
            self.registry.watch_fqn('watcher_idontexist', var2fqn)

        serverid_var1 = self.registry.read_fqn(var1fqn).server_id
        serverid_var2 = self.registry.read_fqn(var2fqn).server_id
        
        # Check watcher states
        self.assertEqual(self.registry.watcher_count_by_server_id(serverid_var1), 2)
        self.assertEqual(self.registry.watcher_count_by_server_id(serverid_var2), 1)
        self.assertEqual(self.registry.node_watcher_count_fqn(var1fqn), 2)
        self.assertEqual(self.registry.node_watcher_count_fqn(var2fqn), 1)

        self.assertEqual(len(callback_history['watcher1']), 0)
        self.assertEqual(len(callback_history['watcher2']), 0)
        
        # Check value updates broadcast
        update1_1 = ValueUpdate(var1_sdk_handle, 123, datetime.now())
        update1_2 = ValueUpdate(var1_sdk_handle, 456, datetime.now())
        update2_1 = ValueUpdate(var2_sdk_handle, 789, datetime.now())
        self.registry.broadcast_value_updates_to_watchers([update1_1, update1_2])
        self.assertEqual(len(callback_history['watcher1']), 1)
        self.assertEqual(len(callback_history['watcher2']), 1)
        self.assertEqual(callback_history['watcher1'][0], [update1_1, update1_2])
        self.assertEqual(callback_history['watcher2'][0], [update1_1, update1_2])

        self.registry.broadcast_value_updates_to_watchers([update2_1])
        self.assertEqual(len(callback_history['watcher1']), 1)
        self.assertEqual(len(callback_history['watcher2']), 2)
        self.assertEqual(callback_history['watcher2'][1], [update2_1])

        self.registry.unwatch_fqn('watcher2', var1fqn)
        self.assertEqual(self.registry.node_watcher_count_fqn(var1fqn), 1)
        self.assertEqual(self.registry.node_watcher_count_fqn(var2fqn), 1)

        update1_3 = ValueUpdate(var1_sdk_handle, 666, datetime.now())
        self.registry.broadcast_value_updates_to_watchers([update1_3])
        self.assertEqual(len(callback_history['watcher1']), 2)
        self.assertEqual(len(callback_history['watcher2']), 2)  # Did not receive the latest update
        self.assertEqual(callback_history['watcher1'][1], [update1_3])

        self.registry.unwatch_fqn('watcher1', var1fqn)
        self.registry.unwatch_fqn('watcher2', var2fqn)
        self.assertEqual(self.registry.node_watcher_count_fqn(var1fqn), 0)
        self.assertEqual(self.registry.node_watcher_count_fqn(var2fqn), 0)

        update1_4 = ValueUpdate(var1_sdk_handle, 777, datetime.now())
        update2_3 = ValueUpdate(var2_sdk_handle, 888, datetime.now())
        self.registry.broadcast_value_updates_to_watchers([update1_4, update2_3])
        # Nothing updated, nobody watches
        self.assertEqual(len(callback_history['watcher1']), 2)
        self.assertEqual(len(callback_history['watcher2']), 2) 
        
        self.registry.unwatch_fqn('watcher1', var1fqn)     # Already unwatched. No error
        
        self.registry.register_watcher('watcher3', lambda *x,**y: None)
        with self.assertRaises(WatchableRegistryError):
            self.registry.watch_fqn('watcher3', 'var:/var/xxx')    # Path exists, but is not a watchable

        with self.assertRaises(WatchableRegistryNodeNotFoundError):
            self.registry.watch_fqn('watcher3', 'var:/idontexist')    # Path does not exist
        
        with self.assertRaises(WatcherNotFoundError):
            self.registry.watch_fqn('unknownwatcher', var1fqn)  # Watcher is not registered
        
    def test_unwatch_on_unregister(self):
        self.registry.write_content(All_DUMMY_DATA) 

        callback_history = {
            'watcher1' : [],
            'watcher2' : [],
            123:[]   
        }
    
        def watch_callback(watcher, value_list):
            callback_history[watcher].append(value_list)

        self.registry.register_watcher('watcher1', watch_callback)
        self.registry.register_watcher('watcher2', watch_callback)
        self.registry.register_watcher(123, watch_callback)
        self.assertEqual(self.registry.registered_watcher_count(), 3)

        with self.assertRaises(WatcherNotFoundError):
            self.registry.unregister_watcher('idontexist')
        
        var1fqn = f'var:/var/xxx/var1'
        var2fqn = f'var:/var/xxx/var2'
        var3fqn = f'var:/var/var3'
       
        var1_sdk_handle = self.make_fake_watchable_from_registry(var1fqn)
        var2_sdk_handle = self.make_fake_watchable_from_registry(var2fqn)
        var3_sdk_handle = self.make_fake_watchable_from_registry(var3fqn)

        self.registry.watch_fqn('watcher1', var1fqn)
        self.registry.watch_fqn('watcher2', var1fqn)
        self.registry.watch_fqn('watcher2', var2fqn)
        self.registry.watch_fqn(123, var3fqn)
        

        update1 = ValueUpdate(var1_sdk_handle, 123, datetime.now())
        update2 = ValueUpdate(var2_sdk_handle, 456, datetime.now())
        update3 = ValueUpdate(var3_sdk_handle, 1.5, datetime.now())
        self.registry.broadcast_value_updates_to_watchers([update1, update2, update3])
        self.assertEqual(len(callback_history['watcher1']), 1)
        self.assertEqual(len(callback_history['watcher2']), 1)
        self.assertEqual(len(callback_history[123]), 1)
        self.assertEqual(self.registry.node_watcher_count_fqn(var1fqn), 2)
        self.assertEqual(self.registry.node_watcher_count_fqn(var2fqn), 1)
        self.assertEqual(self.registry.node_watcher_count_fqn(var3fqn), 1)
        
        self.registry.unregister_watcher('watcher2')
        self.assertEqual(self.registry.registered_watcher_count(), 2)
        self.assertEqual(self.registry.node_watcher_count_fqn(var1fqn), 1)
        self.assertEqual(self.registry.node_watcher_count_fqn(var2fqn), 0)
        self.registry.broadcast_value_updates_to_watchers([update1, update2])
        self.assertEqual(len(callback_history['watcher1']), 2)
        self.assertEqual(len(callback_history['watcher2']), 1)
        
        self.registry.unregister_watcher('watcher1')
        self.assertEqual(self.registry.registered_watcher_count(), 1)
        self.assertEqual(self.registry.node_watcher_count_fqn(var1fqn), 0)
        self.assertEqual(self.registry.node_watcher_count_fqn(var2fqn), 0)
        self.assertEqual(self.registry.node_watcher_count_fqn(var3fqn), 1)
        self.registry.broadcast_value_updates_to_watchers([update1, update2])
        self.assertEqual(len(callback_history['watcher1']), 2)
        self.assertEqual(len(callback_history['watcher2']), 1)
        self.assertEqual(len(callback_history[123]), 1)

        self.registry.unregister_watcher(123)
        self.assertEqual(self.registry.registered_watcher_count(), 0)
        self.assertEqual(self.registry.node_watcher_count_fqn(var1fqn), 0)
        self.assertEqual(self.registry.node_watcher_count_fqn(var2fqn), 0)
        self.assertEqual(self.registry.node_watcher_count_fqn(var3fqn), 0)
        self.registry.broadcast_value_updates_to_watchers([update1, update2, update3])
        self.assertEqual(len(callback_history['watcher1']), 2)
        self.assertEqual(len(callback_history['watcher2']), 1)
        self.assertEqual(len(callback_history[123]), 1)
            
    def test_watch_bad_values(self):
        self.registry.write_content(All_DUMMY_DATA) 
        with self.assertRaises(ValueError):
            self.registry.register_watcher('watcher1', 'iamnotacallback')
        
        with self.assertRaises(ValueError):
            self.registry.register_watcher(None, lambda *x, **y:None)
        
        with self.assertRaises(ValueError):
            self.registry.register_watcher([], lambda *x, **y:None)


    def test_unwatch_on_clear(self):
        clear_funcs = [
            self.registry.clear,
            lambda: self.registry.clear_content_by_type(sdk.WatchableType.Variable)
        ]
        def watch_callback(watcher, wc, value):
            pass   
    
        self.registry.register_watcher('watcher1', watch_callback)
        self.registry.register_watcher('watcher2', watch_callback)

        with self.assertRaises(WatchableRegistryError):
            self.registry.register_watcher('watcher2', watch_callback)  # No override allowed
        self.registry.register_watcher('watcher2', watch_callback,override=True) #override allowed
        
        for clear_func in clear_funcs:
            self.registry.write_content(All_DUMMY_DATA) 


            var1fqn = f'var:/var/xxx/var1'
            var2fqn = f'var:/var/xxx/var2'
            self.registry.watch('watcher1', sdk.WatchableType.Variable, '/var/xxx/var1')
            self.registry.watch_fqn('watcher2', var1fqn)
            self.registry.watch_fqn('watcher2', var2fqn)
            serverid_var1 = self.registry.read_fqn(var1fqn).server_id
            serverid_var2 = self.registry.read_fqn(var2fqn).server_id
            self.assertEqual(self.registry.node_watcher_count_fqn(var1fqn), 2)
            self.assertEqual(self.registry.node_watcher_count_fqn(var2fqn), 1)
            self.assertEqual(self.registry.watched_entries_count(), 2)

            clear_func()
            self.assertEqual(self.registry.watched_entries_count(), 0)

            with self.assertRaises(WatchableRegistryError):
                self.registry.node_watcher_count_fqn(var1fqn)
            with self.assertRaises(WatchableRegistryError):            
                self.registry.node_watcher_count_fqn(var2fqn)

            self.assertEqual(self.registry.watcher_count_by_server_id(serverid_var1), 0)
            self.assertEqual(self.registry.watcher_count_by_server_id(serverid_var2), 0)

            self.registry.write_content({sdk.WatchableType.Variable : DUMMY_DATASET_VAR})
            self.assertEqual(self.registry.node_watcher_count_fqn(var1fqn), 0)
            self.assertEqual(self.registry.node_watcher_count_fqn(var2fqn), 0)
            self.assertEqual(self.registry.watched_entries_count(), 0)

            self.registry.clear()

    def test_bad_values(self):
        self.registry.write_content(All_DUMMY_DATA)

        with self.assertRaises(WatchableRegistryError):
            self.registry.node_watcher_count_fqn('var:/var/xxx')
        
        with self.assertRaises(WatcherNotFoundError):
            self.registry.unwatch_fqn('watcher_xxx', 'var:/var/xxx')
    
    def test_global_watch_callbacks(self):
        self.registry.write_content(All_DUMMY_DATA)

        watch_calls_history = []
        unwatch_calls_history = []

        def watch_callback(watcher_id, display_path, watchable):
            watch_calls_history.append((watcher_id, display_path, watchable))

        def unwatch_callback(watcher_id, display_path, watchable):
            unwatch_calls_history.append((watcher_id, display_path, watchable))

        def dummy_callback(*args, **kwargs):
            pass

        self.registry.register_global_watch_callback(watch_callback, unwatch_callback)

        var1 = self.registry.read_fqn('var:/var/xxx/var1')
        self.registry.register_watcher('watcher1', dummy_callback)
        self.registry.register_watcher('watcher2', dummy_callback)

        self.assertEqual(len(watch_calls_history), 0)
        self.assertEqual(len(unwatch_calls_history), 0)
        self.registry.watch_fqn('watcher1', 'var:/var/xxx/var1')
        self.assertEqual(len(watch_calls_history), 1)
        self.assertEqual(len(unwatch_calls_history), 0)
        self.registry.watch_fqn('watcher2', 'var:/var/xxx/var1')
        self.assertEqual(len(watch_calls_history), 2)
        self.assertEqual(len(unwatch_calls_history), 0)

        self.assertEqual(watch_calls_history[0], ('watcher1', '/var/xxx/var1', var1))
        self.assertEqual(watch_calls_history[1], ('watcher2', '/var/xxx/var1', var1))

        self.registry.unwatch_fqn('watcher1', 'var:/var/xxx/var1')
        self.assertEqual(len(watch_calls_history), 2)
        self.assertEqual(len(unwatch_calls_history), 1)
        self.registry.unwatch_fqn('watcher2', 'var:/var/xxx/var1')
        self.assertEqual(len(watch_calls_history), 2)
        self.assertEqual(len(unwatch_calls_history), 2)

        self.assertEqual(unwatch_calls_history[0], ('watcher1', '/var/xxx/var1', var1))
        self.assertEqual(unwatch_calls_history[1], ('watcher2', '/var/xxx/var1', var1))

    def test_change_counter(self):
        self.assertEqual(self.registry.get_change_counters(), {
            sdk.WatchableType.Variable : 0,
            sdk.WatchableType.RuntimePublishedValue : 0,
            sdk.WatchableType.Alias : 0
        })
        self.registry.write_content( {sdk.WatchableType.Variable: DUMMY_DATASET_VAR} )
        self.assertEqual(self.registry.get_change_counters(), {
            sdk.WatchableType.Variable : 1,
            sdk.WatchableType.RuntimePublishedValue : 0,
            sdk.WatchableType.Alias : 0
        })

        self.registry.write_content({sdk.WatchableType.Alias: DUMMY_DATASET_ALIAS} )
        self.assertEqual(self.registry.get_change_counters(), {
            sdk.WatchableType.Variable : 1,
            sdk.WatchableType.RuntimePublishedValue : 0,
            sdk.WatchableType.Alias : 1
        })

        self.registry.write_content({sdk.WatchableType.RuntimePublishedValue: DUMMY_DATASET_RPV} )
        self.assertEqual(self.registry.get_change_counters(), {
            sdk.WatchableType.Variable : 1,
            sdk.WatchableType.RuntimePublishedValue : 1,
            sdk.WatchableType.Alias : 1
        })

        self.registry.clear_content_by_type(sdk.WatchableType.RuntimePublishedValue)
        self.assertEqual(self.registry.get_change_counters(), {
            sdk.WatchableType.Variable : 1,
            sdk.WatchableType.RuntimePublishedValue : 2,
            sdk.WatchableType.Alias : 1
        })

        self.registry.write_content({sdk.WatchableType.RuntimePublishedValue: DUMMY_DATASET_RPV} )
        self.assertEqual(self.registry.get_change_counters(), {
            sdk.WatchableType.Variable : 1,
            sdk.WatchableType.RuntimePublishedValue : 3,
            sdk.WatchableType.Alias : 1
        })

        self.registry.clear()
        self.assertEqual(self.registry.get_change_counters(), {
            sdk.WatchableType.Variable : 2,
            sdk.WatchableType.RuntimePublishedValue : 4,
            sdk.WatchableType.Alias : 2
        })

        self.registry.write_content(All_DUMMY_DATA)
        self.assertEqual(self.registry.get_change_counters(), {
            sdk.WatchableType.Variable : 3,
            sdk.WatchableType.RuntimePublishedValue : 5,
            sdk.WatchableType.Alias : 3
        })

    def test_get_stats(self):
        self.registry.write_content( All_DUMMY_DATA )
        self.registry.register_watcher('watcher1', lambda *x,**y:None)
        self.registry.register_watcher('watcher2', lambda *x,**y:None)

        var1fqn = f'var:/var/xxx/var1'
        var2fqn = f'var:/var/xxx/var2'
        var3fqn = f'var:/var/var3'
        self.registry.watch_fqn('watcher1', var1fqn)
        self.registry.watch_fqn('watcher2', var1fqn)
        self.registry.watch_fqn('watcher2', var2fqn)
        self.registry.watch_fqn('watcher1', var3fqn)

        stats = self.registry.get_stats()
        self.assertEqual(stats.var_count, len(DUMMY_DATASET_VAR))
        self.assertEqual(stats.alias_count, len(DUMMY_DATASET_ALIAS))
        self.assertEqual(stats.rpv_count, len(DUMMY_DATASET_RPV))
        self.assertEqual(stats.registered_watcher_count, 2)
        self.assertEqual(stats.watched_entries_count, 3)


    def tearDown(self):
        super().tearDown()
