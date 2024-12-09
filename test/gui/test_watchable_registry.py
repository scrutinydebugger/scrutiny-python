#    test_watchable_registry.py
#        A test suite for the WatchableRegistry object
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny import sdk
from scrutiny.gui.core.watchable_registry import WatchableRegistry, WatchableRegistryError, WatchableRegistryNodeContent
from test import ScrutinyUnitTest

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

class TestWatchableRegistry(ScrutinyUnitTest):
    def setUp(self) -> None:
        super().setUp()
        self.registry = WatchableRegistry()

    def test_ignore_empty_data(self):
        self.registry.add_content({
            sdk.WatchableType.Alias : DUMMY_DATASET_ALIAS,
            sdk.WatchableType.RuntimePublishedValue : {}  # Should be ignored
        })

        self.assertTrue(self.registry.has_data(sdk.WatchableType.Alias))
        self.assertFalse(self.registry.has_data(sdk.WatchableType.RuntimePublishedValue))
        self.assertFalse(self.registry.has_data(sdk.WatchableType.Variable))
    
    def test_fqn(self):
        for wt in sdk.WatchableType.get_valids():
            fqn = self.registry.make_fqn(wt, '/a/b/c')
            o = self.registry.parse_fqn(fqn)
            self.assertEqual(o.watchable_type, wt)
            self.assertEqual(o.path, '/a/b/c')
        
        with self.assertRaises(WatchableRegistryError):
            self.registry.parse_fqn('unknown:/a/b/c')
        
        with self.assertRaises(WatchableRegistryError):
            self.registry.parse_fqn('/a/b/c')

        self.assertEqual(WatchableRegistry.extend_fqn('var:/a/b/c', ['x', 'y']), 'var:/a/b/c/x/y')
        self.assertEqual(WatchableRegistry.extend_fqn('var:', ['x', 'y']), 'var:x/y')

        self.assertTrue(WatchableRegistry.fqn_equal('var:/a/b/c', 'var:a/b//c/'))
        self.assertFalse(WatchableRegistry.fqn_equal('var:/a/b/c', 'alias:a/b//c/'))
        self.assertFalse(WatchableRegistry.fqn_equal('var:/a/b/c', 'alias:/a/b/c'))
        
    def test_direct_add_get(self):
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
        
        self.registry.add_watchable_fqn('alias:/a/b/c', obj1)
        self.registry.add_watchable('/a/b/d/e', obj2)   # type is optional when setting
        with self.assertRaises(WatchableRegistryError):
            self.registry.add_watchable_fqn('rpv:/a/b/d/e', obj2)  # type mismatch

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
            self.registry.add_watchable('/', obj1)

    
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

        self.registry.add_watchable('/aaa/bbb', obj1)
        with self.assertRaises(WatchableRegistryError):
            self.registry.add_watchable('/aaa/bbb', obj2)

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

        self.registry.add_watchable('/aaa/bbb', obj1)
        self.registry.add_watchable('/aaa/bbb', obj2)
        
    def test_read_write(self):
        for path, desc in DUMMY_DATASET_VAR.items():
            self.registry.add_watchable(path, desc)
        for path, desc in DUMMY_DATASET_ALIAS.items():
            self.registry.add_watchable(path, desc)
        for path, desc in DUMMY_DATASET_RPV.items():
            self.registry.add_watchable(path, desc)
        

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
        self.registry.add_content(All_DUMMY_DATA)

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
        self.registry.add_content(All_DUMMY_DATA)  
        self.assertTrue(self.registry.has_data(sdk.WatchableType.Variable))
        self.assertTrue(self.registry.has_data(sdk.WatchableType.Alias))
        self.assertTrue(self.registry.has_data(sdk.WatchableType.RuntimePublishedValue))

        had_data = self.registry.clear()
        self.assertTrue(had_data)
        
        self.assertFalse(self.registry.has_data(sdk.WatchableType.Variable))
        self.assertFalse(self.registry.has_data(sdk.WatchableType.Alias))
        self.assertFalse(self.registry.has_data(sdk.WatchableType.RuntimePublishedValue))

        self.assertFalse(self.registry.clear())

    def test_watchers(self):
        self.registry.add_content(All_DUMMY_DATA) 

        callback_history = {
            'watcher1' : [],
            'watcher2' : [],
        }
        def watch_callback(watcher, wc, value):
            callback_history[watcher].append((wc, value))
 
        var1fqn = f'var:/var/xxx/var1'
        var2fqn = f'var:/var/xxx/var2'
        self.registry.watch('watcher1', sdk.WatchableType.Variable, '/var/xxx/var1', watch_callback)
        self.registry.watch_fqn('watcher2', var1fqn, watch_callback)
        self.registry.watch_fqn('watcher2', var2fqn, watch_callback)
        self.assertEqual(self.registry.watched_entries_count(), 2)
        with self.assertRaises(WatchableRegistryError):
            self.registry.watch_fqn('watcher2', var2fqn, watch_callback)

        serverid_var1 = self.registry.read_fqn(var1fqn).server_id
        serverid_var2 = self.registry.read_fqn(var2fqn).server_id
        
        self.assertIsNone(self.registry.get_value(sdk.WatchableType.Variable, '/var/xxx/var1'))
        self.assertIsNone(self.registry.get_value(sdk.WatchableType.Variable, '/var/xxx/var2'))
        self.assertIsNone(self.registry.get_value_fqn(var1fqn))
        self.assertIsNone(self.registry.get_value_fqn(var2fqn))

        self.assertEqual(self.registry.watcher_count_by_server_id(serverid_var1), 2)
        self.assertEqual(self.registry.watcher_count_by_server_id(serverid_var2), 1)
        self.assertEqual(self.registry.watcher_count_fqn(var1fqn), 2)
        self.assertEqual(self.registry.watcher_count_fqn(var2fqn), 1)

        self.assertEqual(len(callback_history['watcher1']), 0)
        self.assertEqual(len(callback_history['watcher2']), 0)
        self.registry.update_watched_entry_value_by_server_id(serverid_var1, 123)
        self.assertEqual(self.registry.get_value_fqn(var1fqn), 123)
        self.assertEqual(len(callback_history['watcher1']), 1)
        self.assertEqual(len(callback_history['watcher2']), 1)
        self.registry.update_watched_entry_value_by_server_id(serverid_var1, 456)
        self.assertEqual(self.registry.get_value_fqn(var1fqn), 456)
        self.assertEqual(len(callback_history['watcher1']), 2)
        self.assertEqual(len(callback_history['watcher2']), 2)
        self.registry.update_watched_entry_value_by_server_id(serverid_var2, 555)
        self.assertEqual(self.registry.get_value_fqn(var2fqn), 555)
        self.assertEqual(len(callback_history['watcher1']), 2)
        self.assertEqual(len(callback_history['watcher2']), 3)


        self.assertEqual(callback_history['watcher1'][0], (self.registry.read_fqn(var1fqn), 123))
        self.assertEqual(callback_history['watcher1'][1], (self.registry.read_fqn(var1fqn), 456))
        
        self.assertEqual(callback_history['watcher2'][0], (self.registry.read_fqn(var1fqn), 123))
        self.assertEqual(callback_history['watcher2'][1], (self.registry.read_fqn(var1fqn), 456))
        self.assertEqual(callback_history['watcher2'][2], (self.registry.read_fqn(var2fqn), 555))

        self.registry.update_watched_entry_value_by_server_id('idontexistanditsfine', 999)    # Silently ignore. No error.

        self.assertEqual(len(callback_history['watcher1']), 2)
        self.assertEqual(len(callback_history['watcher2']), 3)


        self.registry.unwatch_fqn('watcher2', var1fqn)
        self.assertEqual(self.registry.watcher_count_fqn(var1fqn), 1)
        self.assertEqual(self.registry.watcher_count_fqn(var2fqn), 1)

        self.registry.update_watched_entry_value_by_server_id(serverid_var1, 666)
        self.assertEqual(len(callback_history['watcher1']), 3)
        self.assertEqual(len(callback_history['watcher2']), 3)
        self.assertEqual(callback_history['watcher1'][2], (self.registry.read_fqn(var1fqn), 666))

        self.registry.update_value_fqn(var1fqn, 777)
        self.assertEqual(len(callback_history['watcher1']), 4)
        self.assertEqual(len(callback_history['watcher2']), 3)
        self.assertEqual(callback_history['watcher1'][3], (self.registry.read_fqn(var1fqn), 777))

        self.registry.unwatch_fqn('watcher1', var1fqn)
        self.registry.unwatch_fqn('watcher2', var2fqn)
        self.assertEqual(self.registry.watcher_count_fqn(var1fqn), 0)
        self.assertEqual(self.registry.watcher_count_fqn(var2fqn), 0)
        
        self.registry.unwatch_fqn('watcher1', var1fqn, ignore_missing=True)     # Already unwatched. No error

        with self.assertRaises(WatchableRegistryError):
            self.registry.unwatch_fqn('watcher1', var1fqn, ignore_missing=False)


        with self.assertRaises(WatchableRegistryError):
            self.registry.watch_fqn('watcher3', 'var:/var/xxx', watch_callback)    # Path exists, but is not a watchable

        with self.assertRaises(WatchableRegistryError):
            self.registry.update_value_fqn('var:/var/xxx', 123)    # Path exists, but is not a watchable
        
        with self.assertRaises(WatchableRegistryError):
            self.registry.watch_fqn('watcher3', 'var:/idontexist', watch_callback)    # Path does not exist
        
        with self.assertRaises(WatchableRegistryError):
            self.registry.update_value_fqn('var:/idontexist', 123)    # Path does not exist
    
    def test_watch_bad_callback(self):
        self.registry.add_content(All_DUMMY_DATA) 
        with self.assertRaises(ValueError):
            self.registry.watch('watcher1', sdk.WatchableType.Variable, '/var/xxx/var1', 'iamnotacallback')


    def test_unwatch_on_clear(self):
        clear_funcs = [
            self.registry.clear,
            lambda: self.registry.clear_content_by_type(sdk.WatchableType.Variable)
        ]
        for clear_func in clear_funcs:
            self.registry.add_content(All_DUMMY_DATA) 
            def watch_callback(watcher, wc, value):
                pass
    
            var1fqn = f'var:/var/xxx/var1'
            var2fqn = f'var:/var/xxx/var2'
            self.registry.watch('watcher1', sdk.WatchableType.Variable, '/var/xxx/var1', watch_callback)
            self.registry.watch_fqn('watcher2', var1fqn, watch_callback)
            self.registry.watch_fqn('watcher2', var2fqn, watch_callback)
            serverid_var1 = self.registry.read_fqn(var1fqn).server_id
            serverid_var2 = self.registry.read_fqn(var2fqn).server_id
            self.assertEqual(self.registry.watcher_count_fqn(var1fqn), 2)
            self.assertEqual(self.registry.watcher_count_fqn(var2fqn), 1)
            self.assertEqual(self.registry.watched_entries_count(), 2)


            clear_func()
            self.assertEqual(self.registry.watched_entries_count(), 0)

            with self.assertRaises(WatchableRegistryError):
                self.registry.watcher_count_fqn(var1fqn)
            with self.assertRaises(WatchableRegistryError):            
                self.registry.watcher_count_fqn(var2fqn)

            self.assertEqual(self.registry.watcher_count_by_server_id(serverid_var1), 0)
            self.assertEqual(self.registry.watcher_count_by_server_id(serverid_var2), 0)

            self.registry.add_content({sdk.WatchableType.Variable : DUMMY_DATASET_VAR})
            self.assertEqual(self.registry.watcher_count_fqn(var1fqn), 0)
            self.assertEqual(self.registry.watcher_count_fqn(var2fqn), 0)
            self.assertEqual(self.registry.watched_entries_count(), 0)

            self.registry.clear()

    def test_bad_values(self):
        self.registry.add_content(All_DUMMY_DATA)

        with self.assertRaises(WatchableRegistryError):
            self.registry.get_value_fqn('var:/var/xxx')
        
        with self.assertRaises(WatchableRegistryError):
            self.registry.watcher_count_fqn('var:/var/xxx')
        
        with self.assertRaises(WatchableRegistryError):
            self.registry.unwatch_fqn('watcher_xxx', 'var:/var/xxx')
    
    def test_global_watch_callbacks(self):
        self.registry.add_content(All_DUMMY_DATA)

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
        
        self.assertEqual(len(watch_calls_history), 0)
        self.assertEqual(len(unwatch_calls_history), 0)
        self.registry.watch_fqn('watcher1', 'var:/var/xxx/var1', dummy_callback)
        self.assertEqual(len(watch_calls_history), 1)
        self.assertEqual(len(unwatch_calls_history), 0)
        self.registry.watch_fqn('watcher2', 'var:/var/xxx/var1', dummy_callback)
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

    def tearDown(self):
        super().tearDown()
