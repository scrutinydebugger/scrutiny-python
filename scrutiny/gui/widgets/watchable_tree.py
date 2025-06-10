#    watchable_tree.py
#        An enhanced QTreeView with a data model dedicated to Watchables displayed in folder
#        structure.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

__all__ = [
    'get_watchable_icon',
    'NodeSerializableData',
    'WatchableItemSerializableData',
    'FolderItemSerializableData',
    'BaseWatchableRegistryTreeStandardItem',
    'FolderStandardItem',
    'WatchableStandardItem',
    'item_from_serializable_data',
    'WatchableTreeModel',
    'WatchableTreeWidget'
]

from scrutiny.sdk import WatchableType, WatchableConfiguration
from PySide6.QtGui import QStandardItem, QIcon, QKeyEvent
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QModelIndex
from scrutiny.gui import assets
from scrutiny.gui.core.watchable_registry import WatchableRegistry, WatchableRegistryNodeContent
from scrutiny.gui.core.scrutiny_drag_data import WatchableListDescriptor, SingleWatchableDescriptor, ScrutinyDragData
from scrutiny.gui.tools import watchabletype_2_icon
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui.widgets.base_tree import BaseTreeModel, BaseTreeView


from scrutiny.tools.typing import *


def get_watchable_icon(wt: WatchableType) -> QIcon:
    """Return the proper tree icon for a given watchable type (var, alias, rpv)"""
    return scrutiny_get_theme().load_tiny_icon(watchabletype_2_icon(wt))


NodeSerializableType = Literal['watchable', 'folder']


class NodeSerializableData(TypedDict):
    """A serializable dict that represent a tree node"""
    type: NodeSerializableType
    text: str
    fqn: Optional[str]


class WatchableItemSerializableData(NodeSerializableData):
    """A serializable dict that represent a Watchable tree node (leaf node)"""
    pass


class FolderItemSerializableData(NodeSerializableData):
    """A serializable dict that represent a Folder tree node"""
    expanded: bool


class BaseWatchableRegistryTreeStandardItem(QStandardItem):
    """An extension of QT QStandardItem meant to represent either a folder or a watchable

    :param fqn: An optional Fully Qualified Name that point to the relevant element in the Watchable Registry

    """
    _fqn: Optional[str]
    _loaded: bool

    def __init__(self, fqn: Optional[str], *args: Any, **kwargs: Any) -> None:
        self._fqn = fqn
        self._loaded = False
        super().__init__(*args, **kwargs)

    def to_serialized_data(self) -> NodeSerializableData:
        raise NotImplementedError(f"Cannot serialize node of type {self.__class__.__name__}")

    def set_loaded(self) -> None:
        """Mark this node as loaded. USed for (lazy loading)"""
        self._loaded = True

    def is_loaded(self) -> bool:
        """Tells if this node has been loaded (lazy loading)"""
        return self._loaded

    @property
    def fqn(self) -> Optional[str]:
        """Returns the WatchableRegistry Fully Qualified Name if available"""
        return self._fqn


class FolderStandardItem(BaseWatchableRegistryTreeStandardItem):
    """A tree model QStandardItem that represent a folder

    :param text: The text to display in the view
    :param expanded: The expanded/collapse state of that node in the tree
    :param fqn: An optional Fully Qualified Name that point to the relevant element in the Watchable Registry

    """
    _NODE_TYPE: NodeSerializableType = 'folder'
    _expanded: bool
    # fqn is optional for folders. They might be created by the user

    def __init__(self, text: str, expanded: bool = False, fqn: Optional[str] = None):
        folder_icon = scrutiny_get_theme().load_tiny_icon(assets.Icons.Folder)
        super().__init__(fqn, folder_icon, text)
        self._expanded = expanded
        self.setDropEnabled(True)

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded

    def is_expanded(self) -> bool:
        return self._expanded

    @classmethod
    def serialized_node_type(cls) -> NodeSerializableType:
        return cls._NODE_TYPE

    def to_serialized_data(self) -> FolderItemSerializableData:
        """Create a serializable version of this node (using a dict). Used for Drag&Drop"""
        return {
            'type': self.serialized_node_type(),
            'text': self.text(),
            'expanded': self._expanded,
            'fqn': self._fqn
        }

    @classmethod
    def from_serializable_data(cls, data: FolderItemSerializableData) -> "FolderStandardItem":
        """Loads from a serializable dict. Used for Drag&Drop"""
        assert data['type'] == cls.serialized_node_type()
        return FolderStandardItem(
            text=data['text'],
            expanded=data.get('expanded', False),
            fqn=data['fqn']
        )


class WatchableStandardItem(BaseWatchableRegistryTreeStandardItem):
    """A tree model QStandardItem that represent a watchable (leaf node)

    :param watchable_type: The type of watchable
    :param text: The text to display in the view
    :param fqn: An optional Fully Qualified Name that point to the relevant element in the Watchable Registry

    """
    _NODE_TYPE: NodeSerializableType = 'watchable'

    _watchable_type: WatchableType

    def __init__(self, watchable_type: WatchableType, text: str, fqn: str):
        self._watchable_type = watchable_type
        icon = get_watchable_icon(watchable_type)
        super().__init__(fqn, icon, text)
        self.setDropEnabled(False)

    @property
    def fqn(self) -> str:
        """Returns the WatchableRegistry Fully Qualified Name"""
        assert self._fqn is not None
        return self._fqn

    @property
    def watchable_type(self) -> WatchableType:
        return self._watchable_type

    @classmethod
    def serialized_node_type(cls) -> NodeSerializableType:
        return cls._NODE_TYPE

    def to_serialized_data(self) -> WatchableItemSerializableData:
        """Create a serializable version of this node (using a dict). Used for Drag&Drop"""
        return {
            'type': self._NODE_TYPE,
            'text': self.text(),
            'fqn': self.fqn
        }

    @classmethod
    def from_serializable_data(cls, data: WatchableItemSerializableData) -> "Self":
        """Loads from a serializable dict. Used for Drag&Drop"""
        assert data['type'] == cls._NODE_TYPE
        assert data['fqn'] is not None
        parsed = WatchableRegistry.FQN.parse(data['fqn'])

        return cls(
            watchable_type=parsed.watchable_type,
            text=data['text'],
            fqn=data['fqn']
        )

    @classmethod
    def from_drag_watchable_descriptor(cls, desc: SingleWatchableDescriptor) -> "Self":
        """Create from global representation of a watchable defined in the global drag n' drop module"""
        parsed = WatchableRegistry.FQN.parse(desc.fqn)
        return cls(
            watchable_type=parsed.watchable_type,
            text=desc.text,
            fqn=desc.fqn
        )


def item_from_serializable_data(data: NodeSerializableData) -> BaseWatchableRegistryTreeStandardItem:
    if data['type'] == FolderStandardItem._NODE_TYPE:
        return FolderStandardItem.from_serializable_data(cast(FolderItemSerializableData, data))
    if data['type'] == WatchableStandardItem._NODE_TYPE:
        return WatchableStandardItem.from_serializable_data(cast(WatchableItemSerializableData, data))

    raise NotImplementedError(f"Cannot create an item from serializable data of type {data['type']}")


class WatchableTreeModel(BaseTreeModel):
    """Extension of the QT Standard Item Model to represent watchables in a tree. The generic model is specialized to get :
     - Automatic icon choice
     - Leaf nodes that cannot accept children
     - Autofill from the global watchable registry (with possible lazy loading)

    :param parent: The parent 
    :param watchable_registry: A reference to the WatchableRegistry object to feed from

    """
    _watchable_registry: WatchableRegistry

    def __init__(self, parent: QWidget, watchable_registry: WatchableRegistry) -> None:
        super().__init__(parent)
        self._watchable_registry = watchable_registry

    def get_watchable_extra_columns(self, watchable_config: Optional[WatchableConfiguration] = None) -> List[QStandardItem]:
        return []

    def watchable_item_created(self, item: WatchableStandardItem) -> None:
        """Overridable callback called each time a WatchableStandardItem is created"""
        pass

    def folder_item_created(self, item: FolderStandardItem) -> None:
        """Overridable callback called each time a FolderStandardItem is created"""
        pass

    @classmethod
    def make_watchable_row_from_existing_item(cls,
                                              item: WatchableStandardItem,
                                              editable: bool,
                                              extra_columns: List[QStandardItem] = []) -> List[QStandardItem]:
        """Makes a watchable row, i.e. a leaf node in the tree, from an already created first column

        :param item: The first column item
        :param editable: Makes the row editable by the user through the GUI
        :param extra_columns: Columns to add next to the first column

        :return: the list of items in the row
        """
        item.setEditable(editable)
        item.setDragEnabled(True)
        for col in extra_columns:
            col.setDragEnabled(True)
        return [item] + extra_columns

    def make_watchable_row(self,
                           name: str,
                           watchable_type: WatchableType,
                           fqn: str,
                           editable: bool,
                           extra_columns: List[QStandardItem] = []) -> List[QStandardItem]:
        """Makes a watchable row, i.e. a leaf node in the tree

        :param name: The name displayed in the GUI
        :param watchable_type: The watchable type. Define the icon
        :param fqn: The path to the item in the :class:`WatchableRegistry<scrutiny.gui.core.watchable_registry.WatchableRegistry>`
        :param editable: Makes the row editable by the user through the GUI
        :param extra_columns: Columns to add next to the first column

        :return: the list of items in the row
        """
        item = WatchableStandardItem(watchable_type, name, fqn)
        self.watchable_item_created(item)
        return self.make_watchable_row_from_existing_item(item, editable, extra_columns)

    @classmethod
    def make_folder_row_existing_item(cls, item: FolderStandardItem, editable: bool) -> List[QStandardItem]:
        """Creates a folder row from an already existing first column

        :item: The first column item
        :editable: Makes the row editable by the user through the GUI
        """
        item.setEditable(editable)
        item.setDragEnabled(True)
        return [item]

    def make_folder_row(self, name: str, fqn: Optional[str], editable: bool) -> List[QStandardItem]:
        """Creates a folder row

        :param name: The name displayed in the GUI
        :param fqn: The path to the item in the :class:`WatchableRegistry<scrutiny.gui.core.watchable_registry.WatchableRegistry>`
        :editable: Makes the row editable by the user through the GUI
        """
        item = FolderStandardItem(name, expanded=False, fqn=fqn)
        self.folder_item_created(item)
        return self.make_folder_row_existing_item(item, editable)

    def lazy_load(self, parent: BaseWatchableRegistryTreeStandardItem, watchable_type: WatchableType, path: str) -> None:
        """Lazy load a everything under a parent based on the content of the watchable registry

        :param parent: The parent containing the nodes to be loaded
        :param watchable_type: The type of watchable to query to WatchableRegistry
        :param path: The WatchableRegistry path

        """
        self.fill_from_index_recursive(parent, watchable_type, path, max_level=0)

    def fill_from_index_recursive(self,
                                  parent: BaseWatchableRegistryTreeStandardItem,
                                  watchable_type: WatchableType,
                                  path: str,
                                  max_level: Optional[int] = None,
                                  keep_folder_fqn: bool = True,
                                  editable: bool = False,
                                  level: int = 0
                                  ) -> None:
        """Fill the data model from folders and watchable based on the content of the WatchableRegistry

        :param parent: The node to fill
        :param watchable_type: The type of watchable of the parent to query the WatchableRegistry
        :param path: The WatchableRegistry path mapping to the parent.
        :param max_level: The maximum number of nested children. ``None`` for no limit
        :param keep_folder_fqn: Indicate if the Fully Qualified Name taken from  WatchableRegistry should be assigned to folder nodes created
        :param editable: Makes the new nodes editable by the GUI
        :param level: internal parameter to keep track of recursion. The user should leave to default
        """
        parent.set_loaded()
        content = self._watchable_registry.read(watchable_type, path)
        if path.endswith('/'):
            path = path[:-1]

        if isinstance(content, WatchableRegistryNodeContent):  # Equivalent to a folder
            for name in content.subtree:
                subtree_path = f'{path}/{name}'
                folder_fqn: Optional[str] = None
                if keep_folder_fqn:
                    folder_fqn = WatchableRegistry.FQN.make(watchable_type, subtree_path)
                row = self.make_folder_row(
                    name=name,
                    fqn=folder_fqn,
                    editable=editable
                )
                parent.appendRow(row)

                if max_level is None or level < max_level:
                    self.fill_from_index_recursive(
                        parent=cast(BaseWatchableRegistryTreeStandardItem, row[0]),
                        watchable_type=watchable_type,
                        path=subtree_path,
                        editable=editable,
                        max_level=max_level,
                        keep_folder_fqn=keep_folder_fqn,
                        level=level + 1)

            for name, watchable_config in content.watchables.items():
                watchable_path = f'{path}/{name}'
                row = self.make_watchable_row(
                    name=name,
                    watchable_type=watchable_config.watchable_type,
                    fqn=WatchableRegistry.FQN.make(watchable_type, watchable_path),
                    editable=editable,
                    extra_columns=self.get_watchable_extra_columns(watchable_config)
                )
                parent.appendRow(row)

    def make_watchable_list_dragdata_if_possible(self,
                                                 items: Iterable[Optional[BaseWatchableRegistryTreeStandardItem]],
                                                 data_move: Optional[Any] = None
                                                 ) -> Optional[ScrutinyDragData]:
        """Converts a list of tree nodes to a ScrutinyDragData that contains a list of watchable
        only if the given indexes points to watchables (leaf) nodes only. Return ``None`` if any of the element is not a watchable node

        :param items: The items to scan and embed in the drag data
        :param data_move: Additional data to attach to the ScrutinyDragData

        :return: A ScrutinyDragData containing the watchable list or ``None`` if any of the index pointed to something else than a watchable node

        """
        watchables_only = True
        for item in items:
            if item is None or not isinstance(item, WatchableStandardItem):
                watchables_only = False
                break

        if watchables_only:
            watchable_items = cast(List[WatchableStandardItem], items)
            return WatchableListDescriptor(
                data=[SingleWatchableDescriptor(text=item.text(), fqn=item.fqn) for item in watchable_items]
            ).to_drag_data(data_move=data_move)
        return None


class WatchableTreeWidget(BaseTreeView):
    """An extension of the QTreeView dedicated to display a tree of folders and watchables (leaf) nodes.

    :param parent: The parent
    :param model: The model to use. A WatchableTreeModel is required.
    """
    _model: WatchableTreeModel

    DEFAULT_ITEM0_WIDTH = 400
    DEFAULT_ITEM_WIDTH = 100

    def __init__(self, parent: QWidget, model: WatchableTreeModel) -> None:
        super().__init__(parent)
        self._model = model

        self.setModel(self._model)
        self.setUniformRowHeights(True)   # Documentation says it helps performance
        self.setAnimated(False)
        self.header().setStretchLastSection(False)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)

        self.expanded.connect(self._set_expanded_slot)
        self.collapsed.connect(self._set_collapsed_slot)

    def _set_expanded_slot(self, index: QModelIndex) -> None:
        item = self.model().itemFromIndex(index)
        if isinstance(item, FolderStandardItem):
            item.set_expanded(True)

    def _set_collapsed_slot(self, index: QModelIndex) -> None:
        item = self.model().itemFromIndex(index)
        if isinstance(item, FolderStandardItem):
            item.set_expanded(False)

    def set_header_labels(self, headers: List[str]) -> None:
        self._model.setColumnCount(len(headers))
        self._model.setHorizontalHeaderLabels(headers)

    def expand_first_column_to_content(self) -> None:
        """Resize the first column to content if it makes it grow."""
        header = self.header()
        original_sizes = [header.sectionSize(i) for i in range(self._model.columnCount())]
        header.resizeSections(header.ResizeMode.ResizeToContents)

        if header.sectionSize(0) < original_sizes[0]:
            header.resizeSection(0, original_sizes[0])

        for i in range(1, len(original_sizes)):
            header.resizeSection(i, original_sizes[i])

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Some convenient behavior. Ctrl to multiselect. Shift to select a range"""
        if event.key() == Qt.Key.Key_F2:
            self.setCurrentIndex(self.currentIndex().siblingAtColumn(0))
            return super().keyPressEvent(event)
        else:
            return super().keyPressEvent(event)

    def model(self) -> WatchableTreeModel:
        return self._model
