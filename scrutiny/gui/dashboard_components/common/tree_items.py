__all__ = [
    'FolderStandardItem',
    'WatchableStandardItem',
    'StandardItemWithFQN',
]

from scrutiny.sdk import WatchableType
from PySide6.QtGui import  QStandardItem, QIcon
from PySide6.QtCore import  QModelIndex
from scrutiny.gui import assets
from typing import Any

def get_watchable_icon(wt:WatchableType) -> QIcon:
    if wt == WatchableType.Variable:
        return assets.load_icon(assets.Icons.TreeVar)
    if wt == WatchableType.Alias:
        return assets.load_icon(assets.Icons.TreeAlias)
    if wt == WatchableType.RuntimePublishedValue:
        return assets.load_icon(assets.Icons.TreeRpv)
    raise NotImplementedError(f"Unsupported icon for {wt}")

class StandardItemWithFQN(QStandardItem):
    _fqn:str

    def __init__(self, fqn:str, *args:Any, **kwargs:Any) -> None:
        self._fqn = fqn
        super().__init__(*args, **kwargs)

    @property
    def fqn(self) -> str:
        return self._fqn


class FolderStandardItem(StandardItemWithFQN):
    def __init__(self, text:str, fqn:str):
        folder_icon = assets.load_icon(assets.Icons.TreeFolder)
        super().__init__(fqn, folder_icon, text)
    

class WatchableStandardItem(StandardItemWithFQN):
    def __init__(self, watchable_type:WatchableType, text:str, fqn:str):
        icon = get_watchable_icon(watchable_type)
        super().__init__(fqn, icon, text)
