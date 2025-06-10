#    base_tree.py
#        An extension of the QT QTreeView that suits this application. Defines some helper
#        functions and common keyboard/mouse behaviors
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = [
    'SerializableItemIndexDescriptor',
    'BaseTreeModel',
    'BaseTreeView',
]
import functools
import logging

from PySide6.QtGui import QFocusEvent, QStandardItem, QKeyEvent, QStandardItemModel, QColor, QMouseEvent
from PySide6.QtCore import Qt, QModelIndex, QPersistentModelIndex, QAbstractItemModel
from PySide6.QtWidgets import QTreeView, QWidget

from scrutiny.tools.typing import *


class SerializableItemIndexDescriptor(TypedDict):
    """A serializable path to a QStandardItem in a QStandardItemModel. It's a series of row index separated by a /
    example : "2/1/3".
    Used to describe communicate a reference when doing a data move
    """
    path: List[int]
    object_id: int


class BaseTreeModel(QStandardItemModel):
    logger: logging.Logger
    _nesting_col: int

    def __init__(self, parent: QWidget, nesting_col: int = 0) -> None:
        super().__init__(parent)
        self._nesting_col = nesting_col
        if not hasattr(self, 'logger'):
            self.logger = logging.getLogger(self.__class__.__name__)

    def nesting_col(self) -> int:
        return self._nesting_col

    def add_row_to_parent(self, parent: Optional[QStandardItem], row_index: int, row: Sequence[QStandardItem]) -> None:
        """Add a row to a given parent or at the root if no parent is given

        :param parent: The parent of the row to be inserted or ``None`` if the row must be added at the root
        :param row_index: The index of the new row. -1 to append
        :param row: The list of Items that act as a row

        """
        row2 = list(row)    # Make a copy
        while len(row2) > 0 and row2[-1] is None:
            row2 = row2[:-1]  # insert row doesn't like trailing None, but sometime does. Mystery

        if parent is not None:
            if row_index != -1:
                parent.insertRow(row_index, row2)
            else:
                parent.appendRow(row2)
        else:
            if row_index != -1:
                self.insertRow(row_index, row2)
            else:
                self.appendRow(row2)

    def add_multiple_rows_to_parent(self, parent: Optional[QStandardItem], row_index: int, rows: Sequence[Sequence[QStandardItem]]) -> None:
        """Add multiple rows to a given parent or at the root if no parent is given

        :param parent: The parent of the row to be inserted or ``None`` if the row must be added at the root
        :param row_index: The index of the new row. -1 to append
        :param rows: The list of rows

        """
        for row in rows:
            self.add_row_to_parent(parent, row_index, row)
            if row_index != -1:
                row_index += 1

    def moveRow(self,
                source_parent_index: Union[QModelIndex, QPersistentModelIndex],
                sourceRow: int,
                destination_parent_index: Union[QModelIndex, QPersistentModelIndex],
                destinationChild: int) -> bool:
        """Move a row from source to destination

        :param source_parent_index: An index pointing to the parent node. Invalid index if root
        :param sourceRow: The row index of the source under the parent
        :param destination_parent_index: An index pointing to the destination parent node. Invalid index if root
        :param destinationChild: The row number to insert the row under the new parent. -1 to append

        :return: ``True`` on success
        """

        destination_parent: Optional[QStandardItem] = None
        if destination_parent_index.isValid():
            destination_parent = self.itemFromIndex(destination_parent_index)  # get the item before we take a row, it can change it's position

        if source_parent_index == destination_parent_index:
            if destinationChild > sourceRow:
                destinationChild -= 1

        row: Optional[List[QStandardItem]] = None
        if source_parent_index.isValid():
            if sourceRow >= 0:
                row = self.itemFromIndex(source_parent_index).takeRow(sourceRow)
        else:
            if sourceRow >= 0:
                row = self.takeRow(sourceRow)

        if row is not None:
            self.add_row_to_parent(destination_parent, destinationChild, row)

        return True

    def get_item_from_serializable_index_descriptor(self, data: SerializableItemIndexDescriptor) -> Optional[QStandardItem]:
        """Find the item in the data model from a serializable node reference"""
        if 'path' not in data or 'object_id' not in data:
            return None
        path = data['path']
        object_id = data['object_id']
        if not isinstance(path, list) or not isinstance(object_id, int):
            return None
        if len(path) == 0 or object_id == 0:
            return None
        nesting_col = self.nesting_col()
        item = self.item(path[0], nesting_col)
        if item is None:
            return None
        for row_index in path[1:]:
            item = item.child(row_index, nesting_col)
            if item is None:
                return None
        if id(item) != object_id:
            return None
        return item

    def handle_internal_move(self,
                             dest_parent_index: Union[QModelIndex, QPersistentModelIndex],
                             dest_row_index: int,
                             data: List[SerializableItemIndexDescriptor]) -> bool:
        """Handles a row move generated by a drag&drop 

        :param dest_parent_index: The new parent index. invalid index when root
        :param dest_row_index: The row index under the new parent. -1 to append
        :param data: List of serializable references to items in the tree
        :return: ``True`` On success
        """

        try:
            dest_parent = self.itemFromIndex(dest_parent_index)  # Where we move the stuff to
            nesting_col = self.nesting_col()  # The index of the column that stores the main object (watchable/folder)

            # Finds all the items to move
            items = [self.get_item_from_serializable_index_descriptor(descriptor) for descriptor in data]
            if dest_row_index > 0:  # If we do an insert somewhere else than first location (append = -1)
                # Let's take note of what item was before the insert point. We will use it as a reference ton find the insert index
                # When there is many items to move at once because each item will changes all the indexes
                if dest_parent_index.isValid():
                    previous_item = self.itemFromIndex(dest_parent_index).child(dest_row_index - 1, nesting_col)
                else:
                    previous_item = self.item(dest_row_index - 1, nesting_col)

            insert_offset = 0   # The offset since the initial insert point
            for item in items:
                if item is not None:
                    source_parent_index = QModelIndex()
                    if item.parent():
                        source_parent_index = item.parent().index()  # Recompute each time because position can change in the loop

                    # Compute the insert row
                    if dest_row_index == -1:
                        new_dest_row_index = -1  # Append
                    elif dest_row_index == 0:   # Insert at index 0 -->  No previous item.
                        new_dest_row_index = insert_offset
                    else:
                        new_dest_row_index = previous_item.row() + 1 + insert_offset

                    dest_parent_index = QModelIndex()
                    if dest_parent is not None:
                        dest_parent_index = dest_parent.index()  # Recompute each time because position can change in the loop

                    # Move a single element
                    self.moveRow(
                        source_parent_index,
                        item.row(),
                        dest_parent_index,
                        new_dest_row_index
                    )
                    insert_offset += 1
                else:
                    self.logger.error("Item to be moved cannot be found. Ignoring")

        except AssertionError:  # Data has bad format
            return False
        return True

    @classmethod
    def remove_nested_indexes(cls, indexes: Sequence[QModelIndex], columns_to_keep: List[int] = [0]) -> Set[QModelIndex]:
        """Takes a list of indexes and remove any indexes nested under another index part of the input

        :param indexes: The list of indexes to filter
        :param columns_to_keep: A list of column number to keep. Generally wants to leave at 0 since we put children only on column 0

        :return: A set of indexes that has no nested indexes
        """
        indexes_without_nested_values = set([index for index in indexes if index.column() in columns_to_keep])
        # If we have nested nodes, we only keep the parent.
        for index in list(indexes_without_nested_values):   # Make copy
            parent = index.parent()
            while parent.isValid():
                if parent in indexes_without_nested_values:
                    indexes_without_nested_values.remove(index)
                    break
                parent = parent.parent()

        return indexes_without_nested_values

    @classmethod
    def make_serializable_item_index_descriptor(cls, item: Optional[QStandardItem]) -> SerializableItemIndexDescriptor:
        """Create a serializable reference to a tree node"""
        if item is None:
            return {
                'path': [],
                'object_id': 0
            }

        return {
            'path': cls.make_path_list(item),
            'object_id': id(item)
        }

    @classmethod
    def make_path_list(cls, item: QStandardItem) -> List[int]:
        """Describe the location of a tree item with a series of nested row index.
        example  : "2/1/0/4"
        """
        path_list: List[int] = [item.row()]
        index = item.index()
        while index.parent().isValid():
            path_list.insert(0, index.parent().row())
            index = index.parent()
        return path_list

    @classmethod
    def sort_items_by_path(cls, items: Sequence[QStandardItem], top_to_bottom: bool = True) -> None:
        """Sort the a list of tree items by their path. From top to bottom or bottom to top"""
        mult = 1 if top_to_bottom else -1

        def sort_compare(item1: QStandardItem, item2: QStandardItem) -> int:
            path1 = cls.make_path_list(item1)
            path2 = cls.make_path_list(item2)
            len1 = len(path1)
            len2 = len(path2)
            if len1 < len2:
                return -1 * mult
            elif len1 > len2:
                return 1 * mult
            else:
                for i in range(len1):
                    if path1[i] < path2[i]:
                        return -1
                    elif path1[i] > path2[i]:
                        return 1
                return 0

        assert isinstance(items, list)  # mypy workaround. We need the signature to be covariant.
        items.sort(key=functools.cmp_to_key(sort_compare))


class BaseTreeView(QTreeView):

    def setModel(self, model: Optional[QAbstractItemModel]) -> None:
        if not isinstance(model, QStandardItemModel):
            raise ValueError("model must be a QStandardItemModel")
        return super().setModel(model)

    def model(self) -> QStandardItemModel:
        return cast(QStandardItemModel, super().model())

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Some convenient behavior. Ctrl to multiselect. Shift to select a range"""
        if event.key() == Qt.Key.Key_Control:
            self.setSelectionMode(self.SelectionMode.MultiSelection)
        elif event.key() == Qt.Key.Key_Shift:
            self.setSelectionMode(self.SelectionMode.ContiguousSelection)
        elif event.key() == Qt.Key.Key_Escape:
            self.clearSelection()
        else:
            return super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """Some convenient behavior. Ctrl to multiselect. Shift to select a range"""
        if event.key() == Qt.Key.Key_Control:
            if self.selectionMode() == self.SelectionMode.MultiSelection:
                self.setSelectionMode(self.SelectionMode.SingleSelection)
        elif event.key() == Qt.Key.Key_Shift:
            if self.selectionMode() == self.SelectionMode.ContiguousSelection:
                self.setSelectionMode(self.SelectionMode.SingleSelection)
        else:
            return super().keyReleaseEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        # Needs to do that, otherwise holding ctrl/shift and cliking outside of the tree will not detect the key release
        self.setSelectionMode(self.SelectionMode.SingleSelection)
        return super().focusOutEvent(event)

    def set_row_color(self, index: QModelIndex, color: QColor) -> None:
        """Change the background color of a row"""
        item = self.model().itemFromIndex(index)
        for i in range(self.model().columnCount()):
            item = self.model().itemFromIndex(index.siblingAtColumn(i))
            if item is not None:
                item.setBackground(color)

    def is_visible(self, item: QStandardItem) -> bool:
        """Tells if a node is visible, i.e. all parents are expanded.

        :item: The node to check
        :return: ``True`` if visible. ``False`` otherwise
        """
        visible = True
        parent = item.parent()
        while parent is not None:
            if not self.isExpanded(parent.index()):
                visible = False
            parent = parent.parent()
        return visible

    def mousePressEvent(self, event: QMouseEvent) -> None:
        index = self.indexAt(event.pos())
        if event.button() == Qt.MouseButton.RightButton:
            # This condition prevents to change the selection on a right click if it happens on an existing selection
            # Makes it easier to right click a multi-selection (no need to hold shift or control)
            if index.isValid() and index in self.selectedIndexes():
                return  # Don't change the selection
        elif event.button() == Qt.MouseButton.LeftButton:
            if not index.isValid():
                self.clearSelection()
                return

        return super().mousePressEvent(event)
