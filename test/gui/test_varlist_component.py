from test.gui.base_gui_test import ScrutinyBaseGuiTest
from scrutiny.gui.dashboard_components.varlist.varlist_component import VarListComponentTreeModel
from scrutiny.gui.dashboard_components.common.watchable_tree import FolderStandardItem, WatchableStandardItem
from scrutiny.gui.core.watchable_registry import WatchableRegistry
from scrutiny import sdk
from scrutiny.gui.dashboard_components.common.scrutiny_drag_data import ScrutinyDragData

import json

from typing import cast,List,Union

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

TreeItem = Union[FolderStandardItem, WatchableStandardItem]

var_fqn = lambda x: WatchableRegistry.make_fqn(sdk.WatchableType.Variable, x)
alias_fqn = lambda x: WatchableRegistry.make_fqn(sdk.WatchableType.Alias, x)
rpv_fqn = lambda x: WatchableRegistry.make_fqn(sdk.WatchableType.RuntimePublishedValue, x)

class TestVarlistTreeModel(ScrutinyBaseGuiTest):

    registry: WatchableRegistry
    model: VarListComponentTreeModel
    var_node : FolderStandardItem
    alias_node : FolderStandardItem
    rpv_node : FolderStandardItem

    def setUp(self) -> None:
        super().setUp()
        self.registry = WatchableRegistry()
        self.model = VarListComponentTreeModel(parent=None, watchable_registry=self.registry)
        self.registry.add_content({
            sdk.WatchableType.Alias : DUMMY_DATASET_ALIAS,
            sdk.WatchableType.RuntimePublishedValue : DUMMY_DATASET_RPV,
            sdk.WatchableType.Variable : DUMMY_DATASET_VAR,
        })

        var_row = self.model.make_folder_row('Var', self.registry.make_fqn(sdk.WatchableType.Variable, '/'), editable=True)
        alias_row = self.model.make_folder_row('Alias', self.registry.make_fqn(sdk.WatchableType.Alias, '/'), editable=True)
        rpv_row = self.model.make_folder_row('RPV', self.registry.make_fqn(sdk.WatchableType.RuntimePublishedValue, '/'), editable=True)

        self.model.appendRow(var_row)
        self.model.appendRow(alias_row)
        self.model.appendRow(rpv_row)

        self.var_node = cast(FolderStandardItem, var_row[0])
        self.alias_node = cast(FolderStandardItem, alias_row[0])
        self.rpv_node = cast(FolderStandardItem, rpv_row[0])

    def _get_children(self, item:TreeItem) -> List[TreeItem]:
        children = []
        row = 0
        while True:
            child = item.child(row, 0)
            if child is None:
                break
            children.append(child)
            row +=1
        return sorted(children, key=lambda x: x.text())
    
    def _get_children_folder(self, item:TreeItem) -> List[FolderStandardItem]:
        return [x for x in self._get_children(item) if isinstance(x, FolderStandardItem)]
    
    def _get_children_watchable(self, item:TreeItem) -> List[FolderStandardItem]:
        return [x for x in self._get_children(item) if isinstance(x, WatchableStandardItem)]


    def test_fill_from_registry(self):
        self.model.fill_from_index_recursive(self.var_node, sdk.WatchableType.Variable, '/')
        
        self.assertTrue(self.var_node.hasChildren())
        self.assertFalse(self.alias_node.hasChildren())
        self.assertFalse(self.rpv_node.hasChildren())

        children = self._get_children(self.var_node)
        self.assertEqual(len(children), 1)
        var_node = children[0]
        self.assertEqual(var_node.fqn, var_fqn('/var'))

        folders = self._get_children_folder(var_node)
        watchables = self._get_children_watchable(var_node)
        self.assertEqual(len(folders), 1)
        self.assertEqual(len(watchables), 2)

        self.assertEqual(folders[0].fqn, var_fqn('/var/xxx'))
        self.assertEqual(folders[0].text(), 'xxx')
        
        self.assertEqual(watchables[0].fqn, var_fqn('/var/var3'))
        self.assertEqual(watchables[0].text(), 'var3')
        self.assertEqual(watchables[1].fqn, var_fqn('/var/var4'))
        self.assertEqual(watchables[1].text(), 'var4')

        xxx_folder = folders[0]
        folders = self._get_children_folder(xxx_folder)
        watchables = self._get_children_watchable(xxx_folder)
        
        self.assertEqual(len(folders), 0)
        self.assertEqual(len(watchables), 2)

        self.assertEqual(watchables[0].fqn, var_fqn('/var/xxx/var1'))
        self.assertEqual(watchables[0].text(), 'var1')
        self.assertEqual(watchables[1].fqn, var_fqn('/var/xxx/var2'))
        self.assertEqual(watchables[1].text(), 'var2')

    def test_search_by_fqn(self):
        self.model.fill_from_index_recursive(self.var_node, sdk.WatchableType.Variable, '/')
        self.model.fill_from_index_recursive(self.alias_node, sdk.WatchableType.Alias, '/')
        self.model.fill_from_index_recursive(self.rpv_node, sdk.WatchableType.RuntimePublishedValue, '/')

        node = self.model.find_item_by_fqn('alias:/alias/xxx/alias1')
        self.assertIsNotNone(node)

        node = self.model.find_item_by_fqn('alias:/i/dont/exist')
        self.assertIsNone(node)


    def test_drag_mime_single_watchable(self):
        self.model.fill_from_index_recursive(self.var_node, sdk.WatchableType.Variable, '/')
        self.model.fill_from_index_recursive(self.alias_node, sdk.WatchableType.Alias, '/')
        self.model.fill_from_index_recursive(self.rpv_node, sdk.WatchableType.RuntimePublishedValue, '/')

        node = self.model.find_item_by_fqn('alias:/alias/alias2')
        self.assertIsNotNone(node)

        mime_data = self.model.mimeData([node.index()])
        data = ScrutinyDragData.from_mime(mime_data)
        self.assertIsNotNone(data)
        
        self.assertEqual(data.type, ScrutinyDragData.DataType.SingleWatchable)
        self.assertIsNone(data.data_move)
        self.assertIsNotNone(data.data_copy)

        self.assertEqual(data.data_copy['text'], node.text())
        self.assertEqual(data.data_copy['fqn'], node.fqn)
