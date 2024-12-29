#    test_watchable_tree.py
#        Test suite for Custom TreeView widget dedicated to show watchables
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from PySide6.QtGui import QStandardItem
from PySide6.QtCore import QModelIndex, Qt

from scrutiny import sdk
from scrutiny.gui.dashboard_components.common.watchable_tree import WatchableTreeModel
from scrutiny.gui.dashboard_components.varlist.varlist_component import VarListComponentTreeModel
from scrutiny.gui.dashboard_components.watch.watch_component import WatchComponentTreeModel
from scrutiny.gui.dashboard_components.common.watchable_tree import FolderStandardItem, WatchableStandardItem
from scrutiny.gui.core.watchable_registry import WatchableRegistry
from scrutiny.gui.core.scrutiny_drag_data import ScrutinyDragData
from test.gui.base_gui_test import ScrutinyBaseGuiTest

from typing import cast,List,Union,Type, Optional

DUMMY_DATASET_RPV = {
    '/rpv/rpv1000' : sdk.WatchableConfiguration(server_id='rpv_111', watchable_type=sdk.WatchableType.RuntimePublishedValue, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/rpv/rpv1001' : sdk.WatchableConfiguration(server_id='rpv_222', watchable_type=sdk.WatchableType.RuntimePublishedValue, datatype=sdk.EmbeddedDataType.float32, enum=None)
}

DUMMY_DATASET_ALIAS = {
    '/alias/yyy/alias1' : sdk.WatchableConfiguration(server_id='alias_111', watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None),
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

var_fqn = lambda x: WatchableRegistry.FQN.make(sdk.WatchableType.Variable, x)
alias_fqn = lambda x: WatchableRegistry.FQN.make(sdk.WatchableType.Alias, x)
rpv_fqn = lambda x: WatchableRegistry.FQN.make(sdk.WatchableType.RuntimePublishedValue, x)


class BaseWatchableTreeTest(ScrutinyBaseGuiTest):
    registry: WatchableRegistry
    model: WatchableTreeModel
    var_node : FolderStandardItem
    alias_node : FolderStandardItem
    rpv_node : FolderStandardItem

    MODEL_CLASS:Type

    def setUp(self) -> None:
        super().setUp()
        self.registry = WatchableRegistry()
        self.model = self.MODEL_CLASS(parent=None, watchable_registry=self.registry)
        assert isinstance(self.model, WatchableTreeModel)   # base class
        self.registry.write_content({
            sdk.WatchableType.Alias : DUMMY_DATASET_ALIAS,
            sdk.WatchableType.RuntimePublishedValue : DUMMY_DATASET_RPV,
            sdk.WatchableType.Variable : DUMMY_DATASET_VAR,
        })

    
    def load_root_nodes(self):
        var_row = self.model.make_folder_row('Var', WatchableRegistry.FQN.make(sdk.WatchableType.Variable, '/'), editable=True)
        alias_row = self.model.make_folder_row('Alias', WatchableRegistry.FQN.make(sdk.WatchableType.Alias, '/'), editable=True)
        rpv_row = self.model.make_folder_row('RPV', WatchableRegistry.FQN.make(sdk.WatchableType.RuntimePublishedValue, '/'), editable=True)

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

class TestWatchableTree(BaseWatchableTreeTest):

    MODEL_CLASS = WatchableTreeModel
    
    def test_fill_from_registry(self):
        var_row = self.model.make_folder_row('Var', WatchableRegistry.FQN.make(sdk.WatchableType.Variable, '/'), editable=True)
        root_node = var_row[0]
        self.model.appendRow(var_row)
        self.model.fill_from_index_recursive(root_node, sdk.WatchableType.Variable, '/')
        
        self.assertTrue(root_node.hasChildren())


        children = self._get_children(root_node)
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


    def test_add_to_parent(self):
        # Run on root node
        rowA = [QStandardItem(f"A-col{i}") for i in range(5)]
        rowB = [QStandardItem(f"B-col{i}") for i in range(3)]
        rowC = [QStandardItem(f"C-col{i}") for i in range(4)] + [None]

        self.model.add_row_to_parent(None, -1, rowA)
        self.model.add_row_to_parent(None, -1, rowB)
        self.model.add_row_to_parent(None, 1, rowC)

        self.assertEqual(self.model.rowCount(), 3)
        
        self.assertIs(self.model.item(0,0), rowA[0])
        self.assertIs(self.model.item(1,0), rowC[0])
        self.assertIs(self.model.item(2,0), rowB[0])

        self.assertIsNotNone(self.model.item(0,4))
        self.assertIsNotNone(self.model.item(1,3))
        self.assertIsNotNone(self.model.item(2,2))

        self.assertIsNone(self.model.item(1,4))
        self.assertIsNone(self.model.item(2,3))


        # Try on node now
        rowX = [QStandardItem(f"X-col{i}") for i in range(5)]
        rowY = [QStandardItem(f"Y-col{i}") for i in range(3)]
        rowZ = [QStandardItem(f"Z-col{i}") for i in range(4)] + [None]

        parent = rowB[0]

        self.model.add_row_to_parent(parent, -1, rowX)
        self.model.add_row_to_parent(parent, -1, rowY)
        self.model.add_row_to_parent(parent, 1, rowZ)

        self.assertEqual(parent.rowCount(), 3)
        
        self.assertIs(parent.child(0,0), rowX[0])
        self.assertIs(parent.child(1,0), rowZ[0])
        self.assertIs(parent.child(2,0), rowY[0])

        self.assertIsNotNone(parent.child(0,4))
        self.assertIsNotNone(parent.child(1,3))
        self.assertIsNotNone(parent.child(2,2))

        self.assertIsNone(parent.child(1,4))
        self.assertIsNone(parent.child(2,3))


        #Bulk add
        rowI = [QStandardItem(f"I-col{i}") for i in range(5)]
        rowJ = [QStandardItem(f"J-col{i}") for i in range(3)]
        rowK = [QStandardItem(f"K-col{i}") for i in range(4)] + [None]
        rowL = [QStandardItem(f"L-col{i}") for i in range(5)]

        parent = rowA[0]
        self.model.add_multiple_rows_to_parent(parent, -1, [rowI, rowJ])
        self.model.add_multiple_rows_to_parent(parent, 1, [rowK, rowL]) # Insert betweene xisting nodes

        self.assertIs(parent.child(0,0), rowI[0])
        self.assertIs(parent.child(1,0), rowK[0])
        self.assertIs(parent.child(2,0), rowL[0])
        self.assertIs(parent.child(3,0), rowJ[0])

    def test_move_rows(self):
        rowA = [QStandardItem(f"A-col{i}") for i in range(5)]
        rowB = [QStandardItem(f"B-col{i}") for i in range(3)]
        rowC = [QStandardItem(f"C-col{i}") for i in range(4)] + [None]
        rowD = [QStandardItem(f"D-col{i}") for i in range(5)]

        
        self.model.add_multiple_rows_to_parent(None, -1, [rowA, rowB, rowC, rowD])
        invalid_index = QModelIndex()
        self.assertTrue(self.model.moveRow(invalid_index, 0, invalid_index, -1))   # Move A to the end
        self.assertTrue(self.model.moveRow(invalid_index, 2, invalid_index, 0))   # Move D to start

        self.assertIs(self.model.item(0,0), rowD[0])
        self.assertIs(self.model.item(1,0), rowB[0])
        self.assertIs(self.model.item(2,0), rowC[0])
        self.assertIs(self.model.item(3,0), rowA[0])

        rowE = [QStandardItem(f"E-col{i}") for i in range(5)]
        rowF = [QStandardItem(f"F-col{i}") for i in range(5)]
        rowG = [QStandardItem(f"G-col{i}") for i in range(5)]

        self.model.add_multiple_rows_to_parent(rowB[0], -1, [rowE, rowF, rowG])

        self.assertTrue(self.model.moveRow(invalid_index, 3, rowB[0].index(), -1))  # Move A to end of B children
        self.assertTrue(self.model.moveRow(invalid_index, 0, rowB[0].index(), 2))  # Move D to  B children index 2

        self.assertIs(self.model.item(0,0), rowB[0])
        self.assertIs(self.model.item(1,0), rowC[0])
        self.assertIsNone(self.model.item(3,0))

        self.assertIs(rowB[0].child(0,0), rowE[0])
        self.assertIs(rowB[0].child(1,0), rowF[0])
        self.assertIs(rowB[0].child(2,0), rowD[0])
        self.assertIs(rowB[0].child(3,0), rowG[0])
        self.assertIs(rowB[0].child(4,0), rowA[0])
        self.assertIsNone(rowB[0].child(5,0))

        # At this point, we have
        # - B
        #    |-E
        #    |-F
        #    |-D
        #    |-G
        #    |-A
        # - C

        self.assertTrue(self.model.moveRow(rowB[0].index(), 1, rowB[0].index(), -1))  # Move F to end of B children
        self.assertTrue(self.model.moveRow(rowB[0].index(), 2, invalid_index, -1))  # Move G to  end of root
        self.assertTrue(self.model.moveRow(rowB[0].index(), 0, invalid_index, 1))  # Move E to  root index 1

        self.assertIs(self.model.item(0,0), rowB[0])
        self.assertIs(self.model.item(1,0), rowE[0])
        self.assertIs(self.model.item(2,0), rowC[0])
        self.assertIs(self.model.item(3,0), rowG[0])
        self.assertIsNone(self.model.item(4,0))

        self.assertIs(rowB[0].child(0,0), rowD[0])
        self.assertIs(rowB[0].child(1,0), rowA[0])
        self.assertIs(rowB[0].child(2,0), rowF[0])
        self.assertIsNone(rowB[0].child(3,0))

        # At this point, we have
        # - B
        #   |- D
        #   |- A
        #   |- F
        # - E
        # - C
        # - G

        # Test that we can move down. Require special logic to shift while moving
        # Seems weird programmatically, but makes sense on the UI
        self.assertTrue(self.model.moveRow(invalid_index, 0, invalid_index, 2))  # Move B After E

        self.assertIs(self.model.item(0, 0), rowE[0])
        self.assertIs(self.model.item(1, 0), rowB[0])   # Index aut-adjusted to 1 to keep "After E" logic
        self.assertIs(self.model.item(2, 0), rowC[0])
        self.assertIs(self.model.item(3, 0), rowG[0])

    def test_remove_nested_indexes(self):
        rowA = [QStandardItem(f"A-col{i}") for i in range(5)]
        rowB = [QStandardItem(f"B-col{i}") for i in range(5)]
        rowC = [QStandardItem(f"C-col{i}") for i in range(5)]
        rowD = [QStandardItem(f"D-col{i}") for i in range(5)]
        rowE = [QStandardItem(f"E-col{i}") for i in range(5)]
        rowF = [QStandardItem(f"F-col{i}") for i in range(5)]
        rowG = [QStandardItem(f"G-col{i}") for i in range(5)]
        rowH = [QStandardItem(f"H-col{i}") for i in range(5)]

        self.model.add_row_to_parent(None, -1, rowA)
        self.model.add_row_to_parent(None, -1, rowB)
        
        self.model.add_row_to_parent(rowA[0], -1, rowC)
        self.model.add_row_to_parent(rowC[0], -1, rowD)
        self.model.add_row_to_parent(rowC[0], -1, rowE)
        self.model.add_row_to_parent(rowB[0], -1, rowF)
        self.model.add_row_to_parent(rowB[0], -1, rowG)
        self.model.add_row_to_parent(rowG[0], -1, rowH)

        indexes = [rowC[0].index(), rowD[0].index(), rowE[0].index(), rowB[0].index(), rowH[0].index()]
        indexes_fitlered = self.model.remove_nested_indexes(indexes)
        self.assertEqual(len(indexes_fitlered), 2)

        self.assertIn(rowC[0].index(), indexes_fitlered)
        self.assertIn(rowB[0].index(), indexes_fitlered)

        


class TestVarlistTreeModel(BaseWatchableTreeTest):

    MODEL_CLASS = VarListComponentTreeModel
    model : MODEL_CLASS

    def setUp(self) -> None:
        super().setUp()
        self.load_root_nodes()
 

    def test_search_by_fqn(self):
        self.model.fill_from_index_recursive(self.var_node, sdk.WatchableType.Variable, '/')
        self.model.fill_from_index_recursive(self.alias_node, sdk.WatchableType.Alias, '/')
        self.model.fill_from_index_recursive(self.rpv_node, sdk.WatchableType.RuntimePublishedValue, '/')

        node = self.model.find_item_by_fqn('alias:/alias/yyy/alias1')
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
        
        self.assertEqual(data.type, ScrutinyDragData.DataType.WatchableList)
        self.assertIsNone(data.data_move)
        self.assertIsNotNone(data.data_copy)

        self.assertIsInstance(data.data_copy, list)
        self.assertEqual(len(data.data_copy), 1)
        self.assertEqual(data.data_copy[0]['text'], node.text())
        self.assertEqual(data.data_copy[0]['fqn'], node.fqn)

    def test_drag_mime_multiple_watchable(self):
        self.model.fill_from_index_recursive(self.var_node, sdk.WatchableType.Variable, '/')
        self.model.fill_from_index_recursive(self.alias_node, sdk.WatchableType.Alias, '/')
        self.model.fill_from_index_recursive(self.rpv_node, sdk.WatchableType.RuntimePublishedValue, '/')

        node1 = self.model.find_item_by_fqn('alias:/alias/alias2')
        node2 = self.model.find_item_by_fqn('var:/var/xxx/var2')
        self.assertIsNotNone(node1)
        self.assertIsNotNone(node2)

        mime_data = self.model.mimeData([node1.index(), node2.index()])
        data = ScrutinyDragData.from_mime(mime_data)
        self.assertIsNotNone(data)
        
        self.assertEqual(data.type, ScrutinyDragData.DataType.WatchableList)
        self.assertIsNone(data.data_move)
        self.assertIsNotNone(data.data_copy)

        self.assertIsInstance(data.data_copy, list)
        self.assertEqual(len(data.data_copy), 2)
        self.assertEqual(data.data_copy[0]['text'], node1.text())
        self.assertEqual(data.data_copy[0]['fqn'], node1.fqn)
        self.assertEqual(data.data_copy[1]['text'], node2.text())
        self.assertEqual(data.data_copy[1]['fqn'], node2.fqn)

    def test_drag_mime_tree(self):
        self.model.fill_from_index_recursive(self.var_node, sdk.WatchableType.Variable, '/')
        self.model.fill_from_index_recursive(self.alias_node, sdk.WatchableType.Alias, '/')
        self.model.fill_from_index_recursive(self.rpv_node, sdk.WatchableType.RuntimePublishedValue, '/')

        node1 = self.model.find_item_by_fqn('alias:/alias/alias2')
        node2 = self.model.find_item_by_fqn('var:/var/xxx/var2')
        node3 = self.model.find_item_by_fqn('var:/var/xxx') # This is a folder, it changes everything.
        self.assertIsNotNone(node1)
        self.assertIsNotNone(node2)
        self.assertIsNotNone(node3)

        mime_data = self.model.mimeData([node1.index(), node2.index(), node3.index()])
        data = ScrutinyDragData.from_mime(mime_data)
        self.assertIsNotNone(data)
        
        self.assertEqual(data.type, ScrutinyDragData.DataType.WatchableTreeNodesTiedToRegistry)
        self.assertIsNone(data.data_move)
        self.assertIsNotNone(data.data_copy)

        self.assertIsInstance(data.data_copy, list)
        self.assertEqual(len(data.data_copy), 2)    # 2 not 3. var2 is removed because we also have its parent
        self.assertEqual(data.data_copy[0]['type'], 'watchable')
        self.assertEqual(data.data_copy[0]['text'], node1.text())
        self.assertEqual(data.data_copy[0]['fqn'], node1.fqn)

        self.assertEqual(data.data_copy[1]['type'], 'folder')
        self.assertEqual(data.data_copy[1]['text'], node3.text())
        self.assertEqual(data.data_copy[1]['fqn'], node3.fqn)


class TestWatchTreeModel(BaseWatchableTreeTest):

    MODEL_CLASS = WatchComponentTreeModel
    model : MODEL_CLASS

    def setUp(self) -> None:
        super().setUp()
        self.load_root_nodes()

    def get_node(self, name:str) -> WatchableStandardItem:
        items = self.model.findItems(name, Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive)
        self.assertEqual(len(items), 1)
        return items[0]

    def test_decode_serialized_node_ref(self):
        self.model.fill_from_index_recursive(self.var_node, sdk.WatchableType.Variable, '/', keep_folder_fqn=False)
        self.model.fill_from_index_recursive(self.alias_node, sdk.WatchableType.Alias, '/', keep_folder_fqn=False)
        self.model.fill_from_index_recursive(self.rpv_node, sdk.WatchableType.RuntimePublishedValue, '/', keep_folder_fqn=False)

        item = self.model.item(1).child(0,0).child(1,0)
        self.assertIsNotNone(item)
        data = {'path' : [1,0,1], 'object_id' : id(item)}
        item2 = self.model.get_item_from_serializable_index_descriptor(data)
        self.assertIs(item2, item)

        data = {'path' : [1,0,1], 'object_id' : id(item)+1}
        self.assertIsNone(self.model.get_item_from_serializable_index_descriptor(data))
        
        data = {'path' : [1,0,1], 'object_id' : 0}
        self.assertIsNone(self.model.get_item_from_serializable_index_descriptor(data))

        data = {'path' : [1,0,1]}
        self.assertIsNone(self.model.get_item_from_serializable_index_descriptor(data))
       
        data = { 'object_id' : id(item)}
        self.assertIsNone(self.model.get_item_from_serializable_index_descriptor(data))

        data = {'path': 'aaa', 'object_id' : id(item)}
        self.assertIsNone(self.model.get_item_from_serializable_index_descriptor(data))

        data = {'path': [1000,555], 'object_id' : id(item)}
        self.assertIsNone(self.model.get_item_from_serializable_index_descriptor(data))

    def test_refuse_bad_drag_data(self):
        self.model.fill_from_index_recursive(self.var_node, sdk.WatchableType.Variable, '/')
        self.model.fill_from_index_recursive(self.alias_node, sdk.WatchableType.Alias, '/')
        self.model.fill_from_index_recursive(self.rpv_node, sdk.WatchableType.RuntimePublishedValue, '/')

        valid_data_move = [dict(path='0/0', object_id=id(self.model.item(0,0).child(0,0)))]
        self.assertFalse(self.model.canDropMimeData(None, Qt.DropAction.MoveAction, -1, 0, QModelIndex()))
       
        mime_data_fulltree = ScrutinyDragData(ScrutinyDragData.DataType.WatchableFullTree, data_copy={}, data_move=valid_data_move).to_mime()
        mime_data_watchable_list = ScrutinyDragData(ScrutinyDragData.DataType.WatchableList, data_copy=[], data_move=valid_data_move).to_mime()
        mime_data_nodes_tied_to_registry = ScrutinyDragData(ScrutinyDragData.DataType.WatchableTreeNodesTiedToRegistry, data_copy=[], data_move=valid_data_move).to_mime()

        self.assertTrue(self.model.canDropMimeData(mime_data_fulltree, Qt.DropAction.CopyAction, -1, 0, QModelIndex()))
        self.assertTrue(self.model.canDropMimeData(mime_data_fulltree, Qt.DropAction.MoveAction, -1, 0, QModelIndex()))
        self.assertFalse(self.model.canDropMimeData(None, Qt.DropAction.MoveAction, -1, 0, QModelIndex()))
        self.assertFalse(self.model.canDropMimeData(None, Qt.DropAction.CopyAction, -1, 0, QModelIndex()))
        self.assertFalse(self.model.canDropMimeData(mime_data_fulltree, Qt.DropAction.LinkAction, -1, 0, QModelIndex()))

        self.assertTrue(self.model.canDropMimeData(mime_data_watchable_list, Qt.DropAction.CopyAction, -1, 0, QModelIndex()))
        self.assertTrue(self.model.canDropMimeData(mime_data_watchable_list, Qt.DropAction.MoveAction, -1, 0, QModelIndex()))
        self.assertFalse(self.model.canDropMimeData(mime_data_watchable_list, Qt.DropAction.LinkAction, -1, 0, QModelIndex()))     

        self.assertTrue(self.model.canDropMimeData(mime_data_nodes_tied_to_registry, Qt.DropAction.CopyAction, -1, 0, QModelIndex()))
        self.assertFalse(self.model.canDropMimeData(mime_data_nodes_tied_to_registry, Qt.DropAction.MoveAction, -1, 0, QModelIndex()))
        self.assertFalse(self.model.canDropMimeData(mime_data_nodes_tied_to_registry, Qt.DropAction.LinkAction, -1, 0, QModelIndex()))   

        missing_copy_fulltree = ScrutinyDragData(ScrutinyDragData.DataType.WatchableFullTree, data_move=valid_data_move).to_mime()
        missing_move_fulltree = ScrutinyDragData(ScrutinyDragData.DataType.WatchableFullTree, data_copy={}).to_mime()

        self.assertFalse(self.model.canDropMimeData(missing_copy_fulltree, Qt.DropAction.CopyAction, -1, 0, QModelIndex()))
        self.assertFalse(self.model.canDropMimeData(missing_move_fulltree, Qt.DropAction.MoveAction, -1, 0, QModelIndex()))

    def test_drag_mime_single_watchable(self):
        self.model.fill_from_index_recursive(self.var_node, sdk.WatchableType.Variable, '/')
        self.model.fill_from_index_recursive(self.alias_node, sdk.WatchableType.Alias, '/')
        self.model.fill_from_index_recursive(self.rpv_node, sdk.WatchableType.RuntimePublishedValue, '/')

        var2_node = self.get_node('var2')
        assert isinstance(var2_node, WatchableStandardItem)

        mime_data = self.model.mimeData([var2_node.index()])
        data = ScrutinyDragData.from_mime(mime_data)
        self.assertIsNotNone(data)
        
        self.assertEqual(data.type, ScrutinyDragData.DataType.WatchableList)
        self.assertIsNotNone(data.data_move)
        self.assertIsNotNone(data.data_copy)

        self.assertIsInstance(data.data_move, list)
        self.assertEqual(len(data.data_move), 1)
        self.assertIsInstance(data.data_move[0]['path'], list)
        self.assertEqual(len(data.data_move[0]['path']), 4)
        p = data.data_move[0]['path']
        found_node = self.model.item(p[0]).child(p[1]).child(p[2]).child(p[3])
        self.assertIs(found_node, var2_node)
        self.assertEqual(data.data_move[0]['object_id'], id(var2_node))

        self.assertIsInstance(data.data_copy, list)
        self.assertEqual(len(data.data_copy), 1)
        self.assertEqual(data.data_copy[0]['text'], var2_node.text())
        self.assertEqual(data.data_copy[0]['fqn'], var2_node.fqn)   # Watchable have an fqn
    
    def test_drag_mime_multiple_tree(self):
        self.model.fill_from_index_recursive(self.var_node, sdk.WatchableType.Variable, '/', keep_folder_fqn=False)
        self.model.fill_from_index_recursive(self.alias_node, sdk.WatchableType.Alias, '/', keep_folder_fqn=False)
        self.model.fill_from_index_recursive(self.rpv_node, sdk.WatchableType.RuntimePublishedValue, '/', keep_folder_fqn=False)


        var2_node = self.get_node('var2')
        assert isinstance(var2_node, WatchableStandardItem)
        
        folder_yyy = self.get_node('yyy')
        assert isinstance(folder_yyy, FolderStandardItem)

        mime_data = self.model.mimeData([var2_node.index(), folder_yyy.index() ])
        data = ScrutinyDragData.from_mime(mime_data)
        self.assertIsNotNone(data)

        self.assertEqual(data.type, ScrutinyDragData.DataType.WatchableFullTree)
        self.assertIsNotNone(data.data_move)
        self.assertIsNotNone(data.data_copy)

        # Check move data
        self.assertIsInstance(data.data_move, list)
        self.assertEqual(len(data.data_move), 2)

        var2_obj = next(x for x in data.data_move if x['object_id'] == id(var2_node))
        folder_yyy_obj = next(x for x in data.data_move if x['object_id'] == id(folder_yyy))

        self.assertIsNotNone(var2_obj)
        self.assertIsNotNone(folder_yyy_obj)

        self.assertIsInstance(var2_obj['path'], list)
        self.assertEqual(len(var2_obj['path']), 4)
        p = var2_obj['path']
        found_node = self.model.item(p[0]).child(p[1]).child(p[2]).child(p[3])
        self.assertIs(found_node, var2_node)
        self.assertEqual(var2_obj['object_id'], id(var2_node))

        self.assertIsInstance(folder_yyy_obj['path'], list)
        self.assertEqual(len(folder_yyy_obj['path']), 3)
        p = folder_yyy_obj['path']
        found_node = self.model.item(p[0]).child(p[1]).child(p[2])
        self.assertIs(found_node, folder_yyy)
        self.assertEqual(folder_yyy_obj['object_id'], id(folder_yyy))


        # Check copy data
        # We expect 2 trees 
        self.assertIsInstance(data.data_copy, list)
        self.assertEqual(len(data.data_copy), 2)

        # Order is expected to be enforced
        folder_yyy_tree = data.data_copy[0]
        var2_tree = data.data_copy[1]

        self.assertEqual(folder_yyy_tree['node']['type'], 'folder')
        self.assertEqual(folder_yyy_tree['node']['text'], 'yyy')
        self.assertIsNone(folder_yyy_tree['node']['fqn'])   # keep_folder_fqn = False above
        
        self.assertEqual(len(folder_yyy_tree['children']), 1)
        self.assertEqual(folder_yyy_tree['children'][0]['node']['type'], 'watchable')
        self.assertEqual(folder_yyy_tree['children'][0]['node']['text'], 'alias1')
        self.assertEqual(folder_yyy_tree['children'][0]['node']['fqn'], 'alias:/alias/yyy/alias1') 
        
        self.assertEqual(var2_tree['node']['type'], 'watchable')
        self.assertEqual(var2_tree['node']['text'], 'var2')
        self.assertEqual(var2_tree['node']['fqn'], 'var:/var/xxx/var2')
        self.assertEqual(len(var2_tree['children']), 0)

    def test_drop_move_watchable_list(self):
        self.model.fill_from_index_recursive(self.var_node, sdk.WatchableType.Variable, '/', keep_folder_fqn=False)
        self.model.fill_from_index_recursive(self.alias_node, sdk.WatchableType.Alias, '/', keep_folder_fqn=False)
        self.model.fill_from_index_recursive(self.rpv_node, sdk.WatchableType.RuntimePublishedValue, '/', keep_folder_fqn=False)
        
        var2_node = self.get_node('var2')
        assert isinstance(var2_node, WatchableStandardItem)
        
        var3_node = self.get_node('var3')
        assert isinstance(var3_node, WatchableStandardItem)

        folder_yyy_node = self.get_node('yyy')
        assert isinstance(folder_yyy_node, FolderStandardItem)


        mime_data = self.model.mimeData([var2_node.index()])
        data = ScrutinyDragData.from_mime(mime_data)
        self.assertIsNotNone(data)

        self.assertFalse(self.model.canDropMimeData(mime_data, Qt.DropAction.MoveAction, -1, 0, var3_node.index())) # Cannot drop on leaf node
        self.assertTrue(self.model.canDropMimeData(mime_data, Qt.DropAction.MoveAction, -1, 0, folder_yyy_node.index()))

        self.assertTrue(self.model.dropMimeData(mime_data, Qt.DropAction.MoveAction, -1, 0, folder_yyy_node.index()))
        self.assertIs(var2_node.parent(), folder_yyy_node)

    def test_drop_move_full_tree_append(self):
        self.model.fill_from_index_recursive(self.var_node, sdk.WatchableType.Variable, '/', keep_folder_fqn=False)
        self.model.fill_from_index_recursive(self.alias_node, sdk.WatchableType.Alias, '/', keep_folder_fqn=False)
        self.model.fill_from_index_recursive(self.rpv_node, sdk.WatchableType.RuntimePublishedValue, '/', keep_folder_fqn=False)
        
        var2_node = self.get_node('var2')
        assert isinstance(var2_node, WatchableStandardItem)
        
        var3_node = self.get_node('var3')
        assert isinstance(var3_node, WatchableStandardItem)

        folder_yyy_node = self.get_node('yyy')
        assert isinstance(folder_yyy_node, FolderStandardItem)

        folder_xxx_node = self.get_node('xxx')
        assert isinstance(folder_xxx_node, FolderStandardItem)

        folder_rpv_node = self.get_node('rpv')
        assert isinstance(folder_rpv_node, FolderStandardItem)
        self.assertEqual(folder_rpv_node.rowCount(), 2)

        xxx_children_at_beginning = folder_xxx_node.rowCount()
        rpv_children_at_beginning = folder_rpv_node.rowCount()

        mime_data = self.model.mimeData([var2_node.index(), folder_xxx_node.index(), folder_rpv_node.index()])
        data = ScrutinyDragData.from_mime(mime_data)
        self.assertIsNotNone(data)

        self.assertFalse(self.model.canDropMimeData(mime_data, Qt.DropAction.MoveAction, -1, 0, var3_node.index())) # Cannot drop on leaf node
        self.assertTrue(self.model.canDropMimeData(mime_data, Qt.DropAction.MoveAction, -1, 0, folder_yyy_node.index()))

        self.assertTrue(self.model.dropMimeData(mime_data, Qt.DropAction.MoveAction, -1, 0, folder_yyy_node.index()))
        self.assertIs(var2_node.parent(), folder_xxx_node)  # Unchanged bcause var2 is nested into xxx
        self.assertIs(folder_xxx_node.parent(), folder_yyy_node)
        self.assertIs(folder_rpv_node.parent(), folder_yyy_node)

        self.assertEqual(folder_xxx_node.rowCount(), xxx_children_at_beginning )
        self.assertEqual(folder_rpv_node.rowCount(), rpv_children_at_beginning )

        # var2 is not there on purpose. it's nested into another selection (xxx)
        positions = [x.row() for x in cast(List[QStandardItem], [folder_xxx_node, folder_rpv_node])]    
        self.assertCountEqual(positions, [1,2]) # Ensure append

    def test_drop_move_full_tree_insert_index0(self):
        self.model.fill_from_index_recursive(self.var_node, sdk.WatchableType.Variable, '/', keep_folder_fqn=False)
        self.model.fill_from_index_recursive(self.alias_node, sdk.WatchableType.Alias, '/', keep_folder_fqn=False)
        self.model.fill_from_index_recursive(self.rpv_node, sdk.WatchableType.RuntimePublishedValue, '/', keep_folder_fqn=False)
        
        var2_node = self.get_node('var2')
        assert isinstance(var2_node, WatchableStandardItem)
        
        var3_node = self.get_node('var3')
        assert isinstance(var3_node, WatchableStandardItem)

        folder_yyy_node = self.get_node('yyy')
        assert isinstance(folder_yyy_node, FolderStandardItem)

        folder_xxx_node = self.get_node('xxx')
        assert isinstance(folder_xxx_node, FolderStandardItem)

        folder_rpv_node = self.get_node('rpv')
        assert isinstance(folder_rpv_node, FolderStandardItem)
        self.assertEqual(folder_rpv_node.rowCount(), 2)

        xxx_children_at_beginning = folder_xxx_node.rowCount()
        rpv_children_at_beginning = folder_rpv_node.rowCount()

        mime_data = self.model.mimeData([var2_node.index(), folder_xxx_node.index(), folder_rpv_node.index()])
        data = ScrutinyDragData.from_mime(mime_data)
        self.assertIsNotNone(data)

        self.assertFalse(self.model.canDropMimeData(mime_data, Qt.DropAction.MoveAction, 0, 0, var3_node.index())) # Cannot drop on leaf node
        self.assertTrue(self.model.canDropMimeData(mime_data, Qt.DropAction.MoveAction, 0, 0, folder_yyy_node.index()))

        self.assertTrue(self.model.dropMimeData(mime_data, Qt.DropAction.MoveAction, 0, 0, folder_yyy_node.index()))
        self.assertIs(var2_node.parent(), folder_xxx_node)  # Unchanged bcause var2 is nested into xxx
        self.assertIs(folder_xxx_node.parent(), folder_yyy_node)
        self.assertIs(folder_rpv_node.parent(), folder_yyy_node)

        self.assertEqual(folder_xxx_node.rowCount(), xxx_children_at_beginning )
        self.assertEqual(folder_rpv_node.rowCount(), rpv_children_at_beginning )

        # var2 is not there on purpose. it's nested into another selection (xxx)
        positions = [x.row() for x in cast(List[QStandardItem], [folder_xxx_node, folder_rpv_node])]    
        self.assertCountEqual(positions, [0,1]) # insert at 0

    def test_drop_move_full_tree_insert(self):
        self.model.fill_from_index_recursive(self.var_node, sdk.WatchableType.Variable, '/', keep_folder_fqn=False)
        self.model.fill_from_index_recursive(self.alias_node, sdk.WatchableType.Alias, '/', keep_folder_fqn=False)
        self.model.fill_from_index_recursive(self.rpv_node, sdk.WatchableType.RuntimePublishedValue, '/', keep_folder_fqn=False)
        
        rpv1000_node = self.get_node('rpv1000')
        assert isinstance(rpv1000_node, WatchableStandardItem)
        
        rpv1001_node = self.get_node('rpv1001')
        assert isinstance(rpv1001_node, WatchableStandardItem)

        folder_xxx_node = self.get_node('xxx')
        assert isinstance(folder_xxx_node, FolderStandardItem)


        xxx_children_at_beginning = folder_xxx_node.rowCount()

        mime_data = self.model.mimeData([rpv1000_node.index(), rpv1001_node.index()])
        data = ScrutinyDragData.from_mime(mime_data)
        self.assertIsNotNone(data)

        self.assertTrue(self.model.canDropMimeData(mime_data, Qt.DropAction.MoveAction, 1, 0, folder_xxx_node.index()))

        self.assertTrue(self.model.dropMimeData(mime_data, Qt.DropAction.MoveAction, 1, 0, folder_xxx_node.index()))
        self.assertIs(rpv1000_node.parent(), folder_xxx_node) 
        self.assertIs(rpv1001_node.parent(), folder_xxx_node) 

        self.assertEqual(folder_xxx_node.rowCount(), xxx_children_at_beginning+2 )

        # var2 is not there on purpose. it's nested into another selection (xxx)
        positions = [x.row() for x in cast(List[QStandardItem], [rpv1000_node, rpv1001_node])]    
        self.assertCountEqual(positions, [1,2]) # insert at 0 

        var1_node = self.get_node('var1')
        var2_node = self.get_node('var2')
        self.assertIsNotNone(var1_node)
        self.assertIsNotNone(var2_node)

        self.assertEqual(var1_node.row(), 0)
        self.assertEqual(var2_node.row(), 3)

    def test_drop_move_full_tree_insert_at_root(self):
        self.model.fill_from_index_recursive(self.var_node, sdk.WatchableType.Variable, '/', keep_folder_fqn=False)
        self.model.fill_from_index_recursive(self.alias_node, sdk.WatchableType.Alias, '/', keep_folder_fqn=False)
        self.model.fill_from_index_recursive(self.rpv_node, sdk.WatchableType.RuntimePublishedValue, '/', keep_folder_fqn=False)
        
        rpv1000_node = self.get_node('rpv1000')
        assert isinstance(rpv1000_node, WatchableStandardItem)
        
        rpv1001_node = self.get_node('rpv1001')
        assert isinstance(rpv1001_node, WatchableStandardItem)

        root_nodes = [self.var_node, self.rpv_node, self.alias_node]

        root_nodes_by_initial_index = dict(zip([x.row() for x in root_nodes], root_nodes)) # Dict {0 : rpv, 1:alias, 2:var}

        mime_data = self.model.mimeData([rpv1000_node.index(), rpv1001_node.index()])
        data = ScrutinyDragData.from_mime(mime_data)
        self.assertIsNotNone(data)

        invalid_index = QModelIndex()
        self.assertTrue(self.model.canDropMimeData(mime_data, Qt.DropAction.MoveAction, 1, 0, invalid_index))

        self.assertTrue(self.model.dropMimeData(mime_data, Qt.DropAction.MoveAction, 1, 0, invalid_index))
        self.assertIsNone(rpv1000_node.parent()) 
        self.assertIsNone(rpv1001_node.parent()) 

        self.assertEqual(self.model.rowCount(), 5 )

        # var2 is not there on purpose. it's nested into another selection (xxx)
        positions = [x.row() for x in cast(List[QStandardItem], [rpv1000_node, rpv1001_node])]    
        self.assertCountEqual(positions, [1,2]) # insert at 0 

        root_nodes_by_new_index = dict(zip([x.row() for x in root_nodes], root_nodes)) # Dict {0 : rpv, 3:alias, 4:var}
        
        # Ensure shift is correct
        self.assertIs(root_nodes_by_initial_index[0], root_nodes_by_new_index[0])
        self.assertIs(root_nodes_by_initial_index[1], root_nodes_by_new_index[3])
        self.assertIs(root_nodes_by_initial_index[2], root_nodes_by_new_index[4])

    def test_drop_move_full_tree_from_root_to_subfolder(self):

        self.registry.clear()
        self.registry.write_content({
            sdk.WatchableType.Variable: {
                'aaa' : sdk.WatchableConfiguration('aaa', sdk.WatchableType.Variable, sdk.EmbeddedDataType.boolean, None),
                'bbb' : sdk.WatchableConfiguration('bbb', sdk.WatchableType.Variable, sdk.EmbeddedDataType.boolean, None),
                'ccc/ddd' : sdk.WatchableConfiguration('ddd', sdk.WatchableType.Variable, sdk.EmbeddedDataType.boolean, None),
                'eee' : sdk.WatchableConfiguration('eee', sdk.WatchableType.Variable, sdk.EmbeddedDataType.boolean, None),
                'fff' : sdk.WatchableConfiguration('fff', sdk.WatchableType.Variable, sdk.EmbeddedDataType.boolean, None),
            }
        })

        self.model.fill_from_index_recursive(self.var_node, sdk.WatchableType.Variable, '/', keep_folder_fqn=False)

        self.model
        
        aaa_node = self.get_node('aaa')
        bbb_node = self.get_node('bbb')
        eee_node = self.get_node('eee')
        fff_node = self.get_node('fff')
        assert isinstance(aaa_node, WatchableStandardItem)
        assert isinstance(bbb_node, WatchableStandardItem)
        assert isinstance(eee_node, WatchableStandardItem)
        assert isinstance(fff_node, WatchableStandardItem)
        
        # First we put everything at the root because fill_index_from_recursive organize by type
        ccc_folder = self.get_node('ccc')
        assert isinstance(ccc_folder, FolderStandardItem)
        item:QStandardItem
        for item in [aaa_node, bbb_node, ccc_folder, eee_node, fff_node]:
            self.model.moveRow(item.parent().index(), item.row(), QModelIndex(), -1)

        # We have 2 items before the folder, 2 items after folder.   
        # Step 1 : Check that we can move 2nodes AFTER the folder into the folder
        mime_data = self.model.mimeData([eee_node.index(), fff_node.index()])
        data = ScrutinyDragData.from_mime(mime_data)
        self.assertIsNotNone(data)
        self.assertTrue(self.model.canDropMimeData(mime_data, Qt.DropAction.MoveAction, -1, 0, ccc_folder.index()))
        self.assertTrue(self.model.dropMimeData(mime_data, Qt.DropAction.MoveAction, -1, 0, ccc_folder.index()))
        self.assertIs(eee_node.parent(), ccc_folder) 
        self.assertIs(fff_node.parent(), ccc_folder) 

        # Step 2 : Check that we can move 2 nodes BEFORE the folder into the folder
        mime_data = self.model.mimeData([aaa_node.index(), bbb_node.index()])
        data = ScrutinyDragData.from_mime(mime_data)
        self.assertIsNotNone(data)
        self.assertTrue(self.model.canDropMimeData(mime_data, Qt.DropAction.MoveAction, -1, 0, ccc_folder.index()))
        self.assertTrue(self.model.dropMimeData(mime_data, Qt.DropAction.MoveAction, -1, 0, ccc_folder.index()))
        self.assertIs(aaa_node.parent(), ccc_folder) 
        self.assertIs(bbb_node.parent(), ccc_folder) 

    def test_drop_copy_from_watch(self):
        self.model.fill_from_index_recursive(self.var_node, sdk.WatchableType.Variable, '/', keep_folder_fqn=False)
        self.model.fill_from_index_recursive(self.alias_node, sdk.WatchableType.Alias, '/', keep_folder_fqn=False)
        self.model.fill_from_index_recursive(self.rpv_node, sdk.WatchableType.RuntimePublishedValue, '/', keep_folder_fqn=False)
        
        var2_node = self.get_node('var2')
        assert isinstance(var2_node, WatchableStandardItem)
        
        var3_node = self.get_node('var3')
        assert isinstance(var3_node, WatchableStandardItem)

        folder_yyy_node = self.get_node('yyy')
        assert isinstance(folder_yyy_node, FolderStandardItem)

        folder_xxx_node = self.get_node('xxx')
        assert isinstance(folder_xxx_node, FolderStandardItem)

        folder_alias_node = self.get_node('alias')
        assert isinstance(folder_alias_node, FolderStandardItem)

        xxx_row_count_start = folder_xxx_node.rowCount()

        mime_data = self.model.mimeData([folder_yyy_node.index(), var2_node.index()])
        self.assertFalse(self.model.canDropMimeData(mime_data, Qt.DropAction.CopyAction, -1, 0, var3_node.index())) # Cannot drop on leaf node
        self.assertTrue(self.model.canDropMimeData(mime_data, Qt.DropAction.CopyAction, -1, 0, folder_xxx_node.index()))

        self.assertTrue(self.model.dropMimeData(mime_data, Qt.DropAction.CopyAction, -1, 0, folder_xxx_node.index()))
        
        # Did not move existing nodes
        self.assertIs(var2_node.parent(), folder_xxx_node)
        self.assertIs(folder_yyy_node.parent(), folder_alias_node)

        new_childrens = [folder_xxx_node.child(i,0) for i in range(xxx_row_count_start, folder_xxx_node.rowCount()) ]
        self.assertEqual(len(new_childrens), 2)
        if new_childrens[0].text() == 'var2':
            new_var2_node = new_childrens[0]
            new_folder_yyy_node = new_childrens[1]
        else:
            new_var2_node = new_childrens[1]
            new_folder_yyy_node = new_childrens[0]

        assert isinstance(new_var2_node, WatchableStandardItem)
        assert isinstance(new_folder_yyy_node, FolderStandardItem)

        # New nodes are identical, but not the same instance. They're copies
        self.assertIsNot(new_var2_node, var2_node)
        self.assertIsNot(new_folder_yyy_node, folder_yyy_node)

        self.assertEqual(new_var2_node.__class__, var2_node.__class__)
        self.assertEqual(new_var2_node.text(), var2_node.text())
        self.assertEqual(new_var2_node.fqn, var2_node.fqn)

        self.assertEqual(new_folder_yyy_node.__class__, folder_yyy_node.__class__)
        self.assertEqual(new_folder_yyy_node.text(), folder_yyy_node.text())
        self.assertEqual(new_folder_yyy_node.fqn, folder_yyy_node.fqn)
        self.assertEqual(new_folder_yyy_node.rowCount(), folder_yyy_node.rowCount())

        for i in range(new_folder_yyy_node.rowCount()):
            new_child = new_folder_yyy_node.child(i,0)
            old_child = folder_yyy_node.child(i,0)
            self.assertIsNot(old_child, new_child)

            self.assertEqual(old_child.__class__, new_child.__class__)
            self.assertEqual(old_child.text(), new_child.text())
            self.assertEqual(old_child.fqn, new_child.fqn)
            self.assertEqual(old_child.rowCount(), new_child.rowCount())

    def test_drop_copy_from_watch_no_folder(self):
        self.model.fill_from_index_recursive(self.var_node, sdk.WatchableType.Variable, '/', keep_folder_fqn=False)
        self.model.fill_from_index_recursive(self.alias_node, sdk.WatchableType.Alias, '/', keep_folder_fqn=False)
        self.model.fill_from_index_recursive(self.rpv_node, sdk.WatchableType.RuntimePublishedValue, '/', keep_folder_fqn=False)
        
        var2_node = self.get_node('var2')
        assert isinstance(var2_node, WatchableStandardItem)
        
        var3_node = self.get_node('var3')
        assert isinstance(var3_node, WatchableStandardItem)

        folder_xxx_node = self.get_node('xxx')
        assert isinstance(folder_xxx_node, FolderStandardItem)


        xxx_row_count_start = folder_xxx_node.rowCount()

        mime_data = self.model.mimeData([var2_node.index()])
        self.assertFalse(self.model.canDropMimeData(mime_data, Qt.DropAction.CopyAction, -1, 0, var3_node.index())) # Cannot drop on leaf node
        self.assertTrue(self.model.canDropMimeData(mime_data, Qt.DropAction.CopyAction, -1, 0, folder_xxx_node.index()))

        self.assertTrue(self.model.dropMimeData(mime_data, Qt.DropAction.CopyAction, -1, 0, folder_xxx_node.index()))
        
        # Did not move existing nodes
        self.assertIs(var2_node.parent(), folder_xxx_node)

        new_childrens = [folder_xxx_node.child(i,0) for i in range(xxx_row_count_start, folder_xxx_node.rowCount()) ]
        self.assertEqual(len(new_childrens), 1)
        new_var2_node = new_childrens[0]


        assert isinstance(new_var2_node, WatchableStandardItem)

        # New nodes are identical, but not the same instance. They're copies
        self.assertIsNot(new_var2_node, var2_node)

        self.assertEqual(new_var2_node.__class__, var2_node.__class__)
        self.assertEqual(new_var2_node.text(), var2_node.text())
        self.assertEqual(new_var2_node.fqn, var2_node.fqn)


class TestVarlistToWatchDrop(ScrutinyBaseGuiTest):
    registry: WatchableRegistry
    varlist_model: VarListComponentTreeModel
    watch_model: WatchComponentTreeModel
    var_node : FolderStandardItem
    alias_node : FolderStandardItem
    rpv_node : FolderStandardItem

    def setUp(self):
        super().setUp()     
        self.registry = WatchableRegistry()
        self.varlist_model = VarListComponentTreeModel(parent=None, watchable_registry=self.registry)
        self.watch_model = WatchComponentTreeModel(parent=None, watchable_registry=self.registry)
        self.registry.write_content({
            sdk.WatchableType.Alias : DUMMY_DATASET_ALIAS,
            sdk.WatchableType.RuntimePublishedValue : DUMMY_DATASET_RPV,
            sdk.WatchableType.Variable : DUMMY_DATASET_VAR,
        })

        var_row = self.varlist_model.make_folder_row('Var', WatchableRegistry.FQN.make(sdk.WatchableType.Variable, '/'), editable=True)
        alias_row = self.varlist_model.make_folder_row('Alias', WatchableRegistry.FQN.make(sdk.WatchableType.Alias, '/'), editable=True)
        rpv_row = self.varlist_model.make_folder_row('RPV', WatchableRegistry.FQN.make(sdk.WatchableType.RuntimePublishedValue, '/'), editable=True)

        self.varlist_model.appendRow(var_row)
        self.varlist_model.appendRow(alias_row)
        self.varlist_model.appendRow(rpv_row)

        self.var_node = cast(FolderStandardItem, var_row[0])
        self.alias_node = cast(FolderStandardItem, alias_row[0])
        self.rpv_node = cast(FolderStandardItem, rpv_row[0])

        self.varlist_model.fill_from_index_recursive(self.var_node, sdk.WatchableType.Variable, '/')
        self.varlist_model.fill_from_index_recursive(self.alias_node, sdk.WatchableType.Alias, '/')
        self.varlist_model.fill_from_index_recursive(self.rpv_node, sdk.WatchableType.RuntimePublishedValue, '/')

    def reorder_children_by_text(self, items:List[Optional[QStandardItem]], text:List[str]) -> List[QStandardItem]:
        for item in items:
            self.assertIsNotNone(item)
        def generate():
            for name in text:
                found = False
                for item in items:
                    if item.text() == name:
                        yield item
                        found = True
                        break
                if not found:
                    raise RuntimeError(f"Could not find item {name}")
        return tuple(generate())

    def test_drag_varlist_drop_watch_watchable_only(self):
        
        node_alias1 = self.varlist_model.find_item_by_fqn('alias:/alias/yyy/alias1')
        node_var2 = self.varlist_model.find_item_by_fqn('var:/var/xxx/var2')
        self.assertIsNotNone(node_var2)
        self.assertIsNotNone(node_alias1)

        mime_data = self.varlist_model.mimeData([node_var2.index(), node_alias1.index()])
        self.assertIsNotNone(mime_data)

        invalid_index = QModelIndex()

        self.assertFalse(   # Doesn't support move
            self.watch_model.canDropMimeData(mime_data, Qt.DropAction.MoveAction, -1, 0, invalid_index)
            ) 
        
        self.assertTrue(
            self.watch_model.canDropMimeData(mime_data, Qt.DropAction.CopyAction, -1, 0, invalid_index)
            ) # Append on root

        def validate_drop(child1, child2):
            alias1_child, var2_child = self.reorder_children_by_text([child1, child2], [node_alias1.text(), node_var2.text()])

            assert isinstance(var2_child, WatchableStandardItem)
            assert isinstance(alias1_child, WatchableStandardItem)

            self.assertEqual(var2_child.text(), node_var2.text())
            self.assertEqual(var2_child.fqn, node_var2.fqn)

            self.assertEqual(alias1_child.text(), node_alias1.text())
            self.assertEqual(alias1_child.fqn, node_alias1.fqn)


        # Drop root node + append
        self.watch_model.dropMimeData(mime_data, Qt.DropAction.CopyAction, -1, 0, invalid_index)
        self.assertEqual(self.watch_model.rowCount(), 2)
        child1 = self.watch_model.item(0,0)
        child2 = self.watch_model.item(1,0)
        validate_drop(child1, child2)

        # Drop root node + insert
        self.watch_model.dropMimeData(mime_data, Qt.DropAction.CopyAction, 1, 0, invalid_index)
        self.assertEqual(self.watch_model.rowCount(), 4)
        child1 = self.watch_model.item(1,0)
        child2 = self.watch_model.item(2,0)
        validate_drop(child1, child2)


        # Make a folder
        folder_row = self.watch_model.make_folder_row('Some folder', fqn=None, editable=True)
        self.watch_model.add_row_to_parent(None, -1, folder_row)
        folder_node = folder_row[0]


        # drop in folder + append
        self.watch_model.dropMimeData(mime_data, Qt.DropAction.CopyAction, -1, 0, folder_node.index())
        self.assertEqual(folder_node.rowCount(), 2)
        child1 = folder_node.child(0, 0)
        child2 = folder_node.child(1, 0)
        validate_drop(child1, child2)
        
        # Drop folder + insert
        self.watch_model.dropMimeData(mime_data, Qt.DropAction.CopyAction, 1, 0, folder_node.index())
        self.assertEqual(folder_node.rowCount(), 4)
        child1 = folder_node.child(1,0)
        child2 = folder_node.child(2,0)
        validate_drop(child1, child2)
        


    def test_drag_varlist_drop_watch_trees(self):
        node_alias1 = self.varlist_model.find_item_by_fqn('alias:/alias/yyy/alias1')
        node_xxx_folder = self.varlist_model.find_item_by_fqn('var:/var/xxx')
        node_var1 = self.varlist_model.find_item_by_fqn('var:/var/xxx/var1')
        node_var2 = self.varlist_model.find_item_by_fqn('var:/var/xxx/var2')
        self.assertIsNotNone(node_xxx_folder)
        self.assertIsNotNone(node_alias1)
        self.assertIsNotNone(node_var1)
        self.assertIsNotNone(node_var2)
       
        mime_data = self.varlist_model.mimeData([node_xxx_folder.index(), node_alias1.index()])
        self.assertIsNotNone(mime_data)

        invalid_index = QModelIndex()

        self.assertFalse(   # Doesn't support move
            self.watch_model.canDropMimeData(mime_data, Qt.DropAction.MoveAction, -1, 0, invalid_index)
            ) 
        
        self.assertTrue(
            self.watch_model.canDropMimeData(mime_data, Qt.DropAction.CopyAction, -1, 0, invalid_index)
            ) # Append on root


        def validate_drop(arg_child1, arg_child2):
            alias1_child, xxx_folder_child = self.reorder_children_by_text([arg_child1, arg_child2], [node_alias1.text(), node_xxx_folder.text() ])

            assert isinstance(xxx_folder_child, FolderStandardItem)
            assert isinstance(alias1_child, WatchableStandardItem)

            self.assertEqual(xxx_folder_child.text(), node_xxx_folder.text())
            self.assertIsNone(xxx_folder_child.fqn)
            self.assertEqual(xxx_folder_child.rowCount(), 2)
            child1 = xxx_folder_child.child(0,0)
            child2 = xxx_folder_child.child(1,0)

            var1_child, var2_child = self.reorder_children_by_text([child1, child2], [node_var1.text(), node_var2.text() ])
            assert isinstance(var1_child, WatchableStandardItem)
            assert isinstance(var2_child, WatchableStandardItem)

            self.assertEqual(var1_child.text(), node_var1.text())
            self.assertEqual(var1_child.fqn, node_var1.fqn)
            self.assertEqual(var2_child.text(), node_var2.text())
            self.assertEqual(var2_child.fqn, node_var2.fqn)

        # Drop root node + append
        self.watch_model.dropMimeData(mime_data, Qt.DropAction.CopyAction, -1, 0, invalid_index)
        self.assertEqual(self.watch_model.rowCount(), 2)
        child1 = self.watch_model.item(0,0)
        child2 = self.watch_model.item(1,0)
        validate_drop(child1, child2)

        # Drop root node + insert
        self.watch_model.dropMimeData(mime_data, Qt.DropAction.CopyAction, 1, 0, invalid_index)
        self.assertEqual(self.watch_model.rowCount(), 4)
        child1 = self.watch_model.item(1,0)
        child2 = self.watch_model.item(2,0)
        validate_drop(child1, child2)


        # Make a folder
        folder_row = self.watch_model.make_folder_row('Some folder', fqn=None, editable=True)
        self.watch_model.add_row_to_parent(None, -1, folder_row)
        folder_node = folder_row[0]


        # drop in folder + append
        self.watch_model.dropMimeData(mime_data, Qt.DropAction.CopyAction, -1, 0, folder_node.index())
        self.assertEqual(folder_node.rowCount(), 2)
        child1 = folder_node.child(0, 0)
        child2 = folder_node.child(1, 0)
        validate_drop(child1, child2)
        
        # Drop folder + insert
        self.watch_model.dropMimeData(mime_data, Qt.DropAction.CopyAction, 1, 0, folder_node.index())
        self.assertEqual(folder_node.rowCount(), 4)
        child1 = folder_node.child(1,0)
        child2 = folder_node.child(2,0)
        validate_drop(child1, child2)
