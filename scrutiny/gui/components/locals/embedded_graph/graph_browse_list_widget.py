#    graph_browse_list_widget.py
#        A widget that show to the user a list of acquisitions available on the server. Communicate
#        with the Embedded Graph widget through signals
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = [
    'AcquisitionStorageEntryTreeModel',
    'AcquisitionStorageEntryTreeView',
    'GraphBrowseListWidget',
]

from PySide6.QtWidgets import QWidget, QVBoxLayout, QMenu, QAbstractItemDelegate, QLineEdit
from PySide6.QtGui import QStandardItem, QContextMenuEvent, QKeyEvent, QMouseEvent, QAction
from PySide6.QtCore import Signal, QObject, Qt, QModelIndex, QPoint

from scrutiny.sdk import datalogging
from scrutiny.gui.core.persistent_data import gui_persistent_data
from scrutiny.gui.widgets.base_tree import BaseTreeModel, BaseTreeView
from scrutiny.gui import assets
from scrutiny.gui.themes import scrutiny_get_theme

from scrutiny.tools.typing import *
from scrutiny.tools import get_default_val
from scrutiny.gui.tools.invoker import invoke_later


class AcquisitionStorageEntryTreeModel(BaseTreeModel):
    """The model used for the acquisition list treeview"""

    REFERENCE_ID_ROLE = Qt.ItemDataRole.UserRole + 100

    class Columns:
        Date = 0
        Name = 1
        Project = 2
        Version = 3
        FirmwareID = 4

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels([
            "Date",
            "Name",
            "Project",
            "Version",
            "Firmware ID",
        ])

    @classmethod
    def row_from_storage_entry(cls, entry: datalogging.DataloggingStorageEntry) -> List[QStandardItem]:
        datetime_format_str = gui_persistent_data.global_namespace().long_datetime_format()
        row = [
            QStandardItem(entry.timestamp.strftime(datetime_format_str)),
            QStandardItem(entry.name)
        ]

        if entry.firmware_metadata is None:
            row.extend([
                QStandardItem(""),
                QStandardItem(""),
                QStandardItem("")
            ])
        else:
            row.extend([
                QStandardItem(get_default_val(entry.firmware_metadata.project_name, "")),
                QStandardItem(get_default_val(entry.firmware_metadata.version, "")),
                QStandardItem(get_default_val(entry.firmware_id, ""))
            ])

        row[cls.Columns.Name].setData(entry.reference_id, cls.REFERENCE_ID_ROLE)

        for item in row:
            item.setEditable(False)

        return row

    def append_storage_entry(self, entry: datalogging.DataloggingStorageEntry) -> None:
        self.appendRow(self.row_from_storage_entry(entry))

    def update_storage_entry(self, entry: datalogging.DataloggingStorageEntry) -> None:
        """Replace every items in the rows that display the same acquisition (matched by ``reference_id``) """
        for i in range(self.rowCount()):
            reference_id = self.get_reference_id_from_index(self.index(i, 0, QModelIndex()))
            if reference_id == entry.reference_id:
                new_row = self.row_from_storage_entry(entry)

                for j in range(len(new_row)):
                    self.takeItem(i, j)
                    self.setItem(i, j, new_row[j])

    def get_reference_id_from_index(self, index: QModelIndex) -> Optional[str]:
        if not index.isValid():
            return None

        item = self.itemFromIndex(index.siblingAtColumn(self.Columns.Name))
        if item is None:
            return None

        return cast(Optional[str], item.data(self.REFERENCE_ID_ROLE))

    def remove_by_reference_id(self, reference_id: str) -> None:
        items_to_remove: List[QStandardItem] = []
        for i in range(self.rowCount()):
            item = self.item(i, 0)
            if self.get_reference_id_from_index(item.index()) == reference_id:
                items_to_remove.append(item)

        for item in items_to_remove:
            self.removeRow(item.row(), QModelIndex())


class AcquisitionStorageEntryTreeView(BaseTreeView):
    """The treeview extension used for display. No nesting done, just a plain 1-level list"""
    class _Signals(QObject):
        display = Signal()
        delete = Signal()
        rename = Signal(str, str)

    _signals: _Signals
    _item_being_edited: Optional[QStandardItem]
    _previous_name: str

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._signals = self._Signals()
        self._item_being_edited = None
        self._previous_name = ""
        self.setModel(AcquisitionStorageEntryTreeModel(self))
        self.setSortingEnabled(True)
        self.sortByColumn(AcquisitionStorageEntryTreeModel.Columns.Date, Qt.SortOrder.DescendingOrder)

    @property
    def signals(self) -> _Signals:
        return self._signals

    def model(self) -> AcquisitionStorageEntryTreeModel:
        return cast(AcquisitionStorageEntryTreeModel, super().model())

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        context_menu = QMenu(self)
        action_display = context_menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.Eye), "Display")
        action_delete = context_menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.RedX), "Delete")
        action_rename = context_menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.TextEdit), "Rename")

        selected_indexes = self.selectedIndexes()
        selected_indexes_first_col = [index for index in selected_indexes if index.column() == 0]

        action_display.setEnabled(len(selected_indexes_first_col) == 1)
        action_rename.setEnabled(len(selected_indexes_first_col) == 1)
        action_delete.setEnabled(len(selected_indexes_first_col) > 0)

        action_display.triggered.connect(self._signals.display)
        action_delete.triggered.connect(self._signals.delete)
        action_rename.triggered.connect(self._rename_selected_acquisition)

        self.display_context_menu(context_menu, event.pos())

    def display_context_menu(self, menu: QMenu, pos: QPoint) -> None:
        """Display a menu at given relative position, and make sure it goes below the cursor to mimic what most people are used to"""
        actions = menu.actions()
        at: Optional[QAction] = None
        if len(actions) > 0:
            pos += QPoint(0, menu.actionGeometry(actions[0]).height())
            at = actions[0]
        menu.popup(self.mapToGlobal(pos), at)

    def _rename_selected_acquisition(self) -> None:
        """Makes an item in the treeview editable by the user"""
        selected_indexes = self.selectedIndexes()
        selected_indexes_first_col = [index for index in selected_indexes if index.column() == 0]
        if len(selected_indexes_first_col) != 1:
            return

        item_name = self.model().itemFromIndex(selected_indexes_first_col[0].siblingAtColumn(self.model().Columns.Name))
        if item_name is None:
            return

        self._item_being_edited = item_name
        self._previous_name = item_name.text()
        item_name.setEditable(True)
        self.edit(item_name.index())
        item_name.setEditable(False)

        def select_text() -> None:  # Little trick to highlight the text so the user can type right away
            line_edits = cast(List[QLineEdit], self.findChildren(QLineEdit))
            if line_edits is not None and len(line_edits) == 1:
                line_edits[0].selectAll()
        invoke_later(select_text)

    def closeEditor(self, editor: QWidget, hint: QAbstractItemDelegate.EndEditHint) -> None:
        """Called when the user finishes editing an item"""
        if self._item_being_edited is not None:  # We were really editing something. Paranoid check
            item_written = self._item_being_edited

            reference_id = self.model().get_reference_id_from_index(item_written.index())
            new_name = item_written.text()

            must_update = (hint == QAbstractItemDelegate.EndEditHint.SubmitModelCache)  # User pressed Enter, not Escape
            if len(new_name) == 0:  # Name is not acceptable
                item_written.setText(self._previous_name)
                must_update = False

            if must_update:
                self._signals.rename.emit(reference_id, new_name)

        self._item_being_edited = None
        self._previous_name = ""
        return super().closeEditor(editor, hint)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_F2:
            self._rename_selected_acquisition()
        else:
            return super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self._signals.display.emit()
        return super().mouseDoubleClickEvent(event)

    def update_storage_entry(self, entry: datalogging.DataloggingStorageEntry) -> None:
        self.model().update_storage_entry(entry)


class GraphBrowseListWidget(QWidget):
    """A continer widget that is the public API. Wraps the treeview"""

    class _Signals(QObject):
        display = Signal(str)
        delete = Signal(list)
        delete_all = Signal()
        rename = Signal(str, str)

    _signals: _Signals
    _treeview: AcquisitionStorageEntryTreeView

    @property
    def signals(self) -> _Signals:
        return self._signals

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._signals = self._Signals()
        self._treeview = AcquisitionStorageEntryTreeView(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._treeview)

        self._treeview.signals.display.connect(self._emit_display_signal_if_possible)
        self._treeview.signals.delete.connect(self._emit_delete_signal_if_possible)
        self._treeview.signals.rename.connect(self._signals.rename)  # Bubble up the signal

    def clear(self) -> None:
        """Remove every acquisition from the list"""
        self._treeview.model().removeRows(0, self._treeview.model().rowCount())

    def add_storage_entries(self, entries: Sequence[datalogging.DataloggingStorageEntry]) -> None:
        """Add some entries to the list"""
        self._treeview.setSortingEnabled(False)
        for entry in entries:
            self._treeview.model().append_storage_entry(entry)
        self._treeview.setSortingEnabled(True)

    def autosize_columns(self) -> None:
        for i in range(self._treeview.model().columnCount()):
            self._treeview.resizeColumnToContents(i)

    def update_storage_entry(self, entry: datalogging.DataloggingStorageEntry) -> None:
        """Request a change to an entry. Teh ``reference_id`` field is used to find the update target"""
        self._treeview.setSortingEnabled(False)
        self._treeview.update_storage_entry(entry)
        self._treeview.setSortingEnabled(True)

    def _emit_display_signal_if_possible(self) -> None:
        """Request a display of the selected acquisition in the list"""
        selected_indexes = self._treeview.selectedIndexes()
        selected_indexes_one_per_row = [index for index in selected_indexes if index.column() == 0]
        model = self._treeview.model()
        if len(selected_indexes_one_per_row) == 1:
            reference_id = model.get_reference_id_from_index(selected_indexes_one_per_row[0])
            if reference_id is not None:
                self._signals.display.emit(reference_id)

    def _emit_delete_signal_if_possible(self) -> None:
        """Request a delete for the selected acquisition in the list"""
        selected_indexes = self._treeview.selectedIndexes()
        selected_indexes_one_per_row = [index for index in selected_indexes if index.column() == 0]
        model = self._treeview.model()
        if len(selected_indexes_one_per_row) > 0:
            to_delete: List[str] = []
            for index in selected_indexes_one_per_row:
                reference_id = model.get_reference_id_from_index(index)
                if reference_id is not None:
                    to_delete.append(reference_id)
            if len(to_delete) > 0:
                self._signals.delete.emit(to_delete)

    def remove_by_reference_id(self, reference_id: str) -> None:
        """Remove an acquisition from the list. Acquisition identified by its unique ``reference_id`` field"""
        self._treeview.model().remove_by_reference_id(reference_id)
