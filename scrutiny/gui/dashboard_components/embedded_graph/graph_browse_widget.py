from PySide6.QtWidgets import  QWidget, QVBoxLayout, QPushButton, QMenu, QAbstractItemDelegate, QMessageBox
from PySide6.QtGui import  QStandardItem, QContextMenuEvent
from PySide6.QtCore import Signal, QObject, Qt, QModelIndex

from scrutiny.sdk import datalogging
from scrutiny.gui.core.preferences import gui_preferences
from scrutiny.gui.dashboard_components.common.base_tree import BaseTreeModel, BaseTreeView
from scrutiny.gui import assets

from scrutiny.tools.typing import *
from scrutiny.tools import get_default_val

class AcquisitionStorageEntryTreeModel(BaseTreeModel):
    REFERENCE_ID_ROLE = Qt.ItemDataRole.UserRole + 100

    class Columns:
        Date = 0
        Name = 1
        Project = 2
        Version = 3
        FirmwareID = 4

    def __init__(self, parent:QWidget) -> None:
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
    def row_from_storage_entry(cls, entry:datalogging.DataloggingStorageEntry) -> List[QStandardItem]:
        datatime_format_str = gui_preferences.global_namespace().long_datetime_format()
        row = [
            QStandardItem(entry.timestamp.strftime(datatime_format_str)),
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

    def append_storage_entry(self, entry:datalogging.DataloggingStorageEntry) -> None:
        self.appendRow(self.row_from_storage_entry(entry))
    
    def get_reference_id_from_index(self, index:QModelIndex) -> Optional[str]:
        if not index.isValid():
            return None
        
        item = self.itemFromIndex(index.siblingAtColumn(self.Columns.Name))
        if item is None:
            return None
        
        return cast(Optional[str], item.data(self.REFERENCE_ID_ROLE))

class AcquisitionStorageEntryTreeView(BaseTreeView):
    class _Signals(QObject):
        display = Signal()
        delete = Signal()
        rename = Signal(str,str)

    _signals:_Signals
    _previous_name:str

    def __init__(self, parent:QWidget) -> None:
        super().__init__(parent)
        self._signals = self._Signals()
        self._previous_name = ""
        self.setModel(AcquisitionStorageEntryTreeModel(self))
        self.setSortingEnabled(True)
        self.sortByColumn(AcquisitionStorageEntryTreeModel.Columns.Date, Qt.SortOrder.DescendingOrder)

    @property
    def signals(self) -> _Signals:
        return self._signals

    def model(self) -> AcquisitionStorageEntryTreeModel:
        return cast(AcquisitionStorageEntryTreeModel, super().model())

    def contextMenuEvent(self, event:QContextMenuEvent) -> None:
        context_menu = QMenu(self)
        action_display = context_menu.addAction(assets.load_tiny_icon(assets.Icons.Eye), "Display")
        action_delete = context_menu.addAction(assets.load_tiny_icon(assets.Icons.RedX), "Delete")
        action_rename = context_menu.addAction(assets.load_tiny_icon(assets.Icons.TextEdit), "Rename")

        selected_indexes = self.selectedIndexes()
        selected_indexes_first_col = [index for index in selected_indexes if index.column() == 0]
        
        action_display.setEnabled(len(selected_indexes_first_col) == 1)
        action_rename.setEnabled(len(selected_indexes_first_col) == 1)
        action_delete.setEnabled(len(selected_indexes_first_col) > 0)
        
        action_display.triggered.connect(self._signals.display)
        action_delete.triggered.connect(self._signals.delete)
        action_rename.triggered.connect(self._rename_acquisition)

        context_menu.popup(self.mapToGlobal(event.pos()))
    
    def _rename_acquisition(self) -> None:
        selected_indexes = self.selectedIndexes()
        selected_indexes_first_col = [index for index in selected_indexes if index.column() == 0]
        if len(selected_indexes_first_col) != 1:
            return 
        
        item_name = self.model().itemFromIndex(selected_indexes_first_col[0].siblingAtColumn(self.model().Columns.Name))
        if item_name is None:
            return
        
        self._previous_name = item_name.text()
        item_name.setEditable(True)
        self.edit(item_name.index())
        item_name.setEditable(False)
    
    def closeEditor(self, editor:QWidget, hint:QAbstractItemDelegate.EndEditHint) -> None:
        item_written = self.model().itemFromIndex(self.currentIndex())
        
        reference_id = self.model().get_reference_id_from_index(item_written.index())
        new_name = item_written.text()

        must_update = True
        if len(new_name) == 0:
            item_written.setText(self._previous_name)
            must_update = False
        
        if must_update:
            self._signals.rename.emit(reference_id, new_name)
        
        return super().closeEditor(editor, hint)
        

class GraphBrowseWidget(QWidget):

    class _Signals(QObject):
        display = Signal(str)
        delete = Signal(list)
        delete_all = Signal()
        rename = Signal(str,str)

    _signals:_Signals
    _treeview:AcquisitionStorageEntryTreeView 

    @property
    def signals(self) -> _Signals:
        return self._signals

    def __init__(self, parent:QWidget):
        super().__init__(parent)
        self._signals = self._Signals()
        self._treeview = AcquisitionStorageEntryTreeView(self)
        self._btn_display = QPushButton("Display")
        self._btn_delete_all = QPushButton("Delete All")
        self._btn_display.clicked.connect(self._emit_display_signal_if_possible)
        self._btn_delete_all.clicked.connect(self._btn_delete_all_clicked_slot)

        layout = QVBoxLayout(self)
        layout.addWidget(self._treeview)
        layout.addWidget(self._btn_display)
        layout.addWidget(self._btn_delete_all)

        self._treeview.signals.display.connect(self._emit_display_signal_if_possible)
        self._treeview.signals.delete.connect(self._emit_delete_signal_if_possible)
        self._treeview.signals.rename.connect(self._signals.rename) # Bubble up the signal
    
    def clear(self) -> None:
        self._treeview.model().removeRows(0, self._treeview.model().rowCount())
    
    def add_storage_entries(self, entries:Sequence[datalogging.DataloggingStorageEntry]) -> None:
        self._treeview.setSortingEnabled(False)
        for entry in entries:
            self._treeview.model().append_storage_entry(entry)
        self._treeview.setSortingEnabled(True)
    
    def _btn_delete_all_clicked_slot(self) -> None:
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Icon.Warning)
        msgbox.setWindowTitle("Are you sure?")
        msgbox.setText("You are about to delete all datalogging acquisition on the server.\nProceed?")
        msgbox.setStandardButtons(QMessageBox.StandardButton.No | QMessageBox.StandardButton.Yes)
        msgbox.setDefaultButton(QMessageBox.StandardButton.No)

        msgbox.setModal(True)
        reply = msgbox.exec()

        if reply == QMessageBox.StandardButton.Yes:
            self._signals.delete_all.emit()
            
        

    def _emit_display_signal_if_possible(self) -> None:
        selected_indexes = self._treeview.selectedIndexes()
        selected_indexes_one_per_row = [index for index in selected_indexes if index.column() == 0]
        model = self._treeview.model()
        if len(selected_indexes_one_per_row) == 1:
            reference_id = model.get_reference_id_from_index(selected_indexes_one_per_row[0])
            if reference_id is not None:
                self._signals.display.emit(reference_id)

    def _emit_delete_signal_if_possible(self) -> None:
        selected_indexes = self._treeview.selectedIndexes()
        selected_indexes_one_per_row = [index for index in selected_indexes if index.column() == 0]
        model = self._treeview.model()
        if len(selected_indexes_one_per_row) > 0:
            to_delete:List[str] = []
            for index in selected_indexes_one_per_row:
                reference_id = model.get_reference_id_from_index(index)
                if reference_id is not None:
                    to_delete.append(reference_id)
            if len(to_delete) > 0:
                self._signals.delete.emit(to_delete)
            
