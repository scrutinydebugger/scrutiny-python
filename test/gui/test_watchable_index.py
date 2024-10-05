from scrutiny import sdk
from scrutiny.gui.watchable_index import WatchableIndex,WatchableIndexError
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

class TestWatchableIndex(ScrutinyUnitTest):
    def setUp(self) -> None:
        super().setUp()
        self.index = WatchableIndex()

    def test_ignore_empty_data(self):
        self.index.add_content({
            sdk.WatchableType.Alias : DUMMY_DATASET_ALIAS,
            sdk.WatchableType.RuntimePublishedValue : {}  # Should be ignored
        })

        self.assertTrue(self.index.has_data(sdk.WatchableType.Alias))
        self.assertFalse(self.index.has_data(sdk.WatchableType.RuntimePublishedValue))
        self.assertFalse(self.index.has_data(sdk.WatchableType.Variable))
    
    def test_fqn(self):
        for wt in sdk.WatchableType.get_valids():
            fqn = self.index.make_fqn(wt, '/a/b/c')
            o = self.index.parse_fqn(fqn)
            self.assertEqual(o.watchable_type, wt)
            self.assertEqual(o.path, '/a/b/c')
        
        with self.assertRaises(WatchableIndexError):
            self.index.parse_fqn('unknown:/a/b/c')
        
        with self.assertRaises(WatchableIndexError):
            self.index.parse_fqn('/a/b/c')
        
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
        
        self.index.add_watchable_fqn('alias:/a/b/c', obj1)
        self.index.add_watchable('/a/b/d/e', obj2)   # type is optional when setting
        with self.assertRaises(WatchableIndexError):
            self.index.add_watchable_fqn('rpv:/a/b/d/e', obj2)  # type mismatch

        o1 = self.index.read(sdk.WatchableType.Alias, '/a/b/c')
        self.assertIs(o1, obj1)
        with self.assertRaises(WatchableIndexError):
            self.index.read(sdk.WatchableType.Variable, '/a/b/c')
        
        o2 = self.index.read_fqn('var:/a/b/d/e')
        self.assertIs(obj2, o2)

    def test_root_not_writable(self):
        obj1 = sdk.WatchableConfiguration(
            server_id="aaa",
            watchable_type=sdk.WatchableType.Alias,
            datatype=sdk.EmbeddedDataType.float32,
            enum=None
        )

        with self.assertRaises(WatchableIndexError):
            self.index.add_watchable('/', obj1)

    
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

        self.index.add_watchable('/aaa/bbb', obj1)
        with self.assertRaises(WatchableIndexError):
            self.index.add_watchable('/aaa/bbb', obj2)

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

        self.index.add_watchable('/aaa/bbb', obj1)
        self.index.add_watchable('/aaa/bbb', obj2)
        
    def test_read_write(self):
        for path, desc in DUMMY_DATASET_VAR.items():
            self.index.add_watchable(path, desc)
        for path, desc in DUMMY_DATASET_ALIAS.items():
            self.index.add_watchable(path, desc)
        for path, desc in DUMMY_DATASET_RPV.items():
            self.index.add_watchable(path, desc)
        

        node = self.index.read_fqn('var:/')
        assert isinstance(node, WatchableIndex.NodeContent)
        self.assertEqual(len(node.watchables), 0)
        self.assertEqual(len(node.subtree), 1)

        self.assertIn('var', node.subtree)


        node = self.index.read_fqn('var:/var')
        assert isinstance(node, WatchableIndex.NodeContent)
        self.assertEqual(len(node.watchables), 2)
        self.assertEqual(len(node.subtree), 1)

        self.assertIn('xxx', node.subtree)
        self.assertIn(DUMMY_DATASET_VAR['/var/var3'], node.watchables)
        self.assertIn(DUMMY_DATASET_VAR['/var/var4'], node.watchables)


        node = self.index.read_fqn('var:/var/xxx')
        assert isinstance(node, WatchableIndex.NodeContent)
        self.assertEqual(len(node.watchables), 2)
        self.assertEqual(len(node.subtree), 0)

        self.assertIn(DUMMY_DATASET_VAR['/var/xxx/var1'], node.watchables)
        self.assertIn(DUMMY_DATASET_VAR['/var/xxx/var2'], node.watchables)


    def tearDown(self):
        super().tearDown()
