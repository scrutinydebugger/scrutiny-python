__all__ = [
    'get',
    'load_bin',
    'load_text',
    'logo_icon',
    'load_pixmap',
    'load_icon',
    'Icons'
]

import os
from scrutiny.gui.core.exceptions import GuiError
from pathlib import Path
from PySide6.QtGui import QPixmap, QIcon

from typing import List, Union, Dict

ASSET_PATH = os.path.dirname(__file__)


def get(name:Union[str, List[str]]) -> Path:
    if isinstance(name, list):
        name=os.path.join(*name)

    outpath = os.path.join(ASSET_PATH, name)
    if os.path.commonpath([outpath, ASSET_PATH]) != ASSET_PATH:
        raise GuiError("Directory traversal while reading an asset")
    return Path(outpath)

def load_bin(name:Union[str, List[str]]) -> bytes:
    with open(get(name), 'rb') as f:
        return f.read()

def load_text(name:Union[str, List[str]]) -> str:
    with open(get(name), 'r') as f:
        return f.read() 

def logo_icon() -> Path:
    return get('scrutiny-logo-square-64x64.png')

def load_pixmap(name:str) -> QPixmap:
    if name not in pixmap_cache:
        pixmap_cache[name] = QPixmap(str(get(name)))
    return pixmap_cache[name]

def load_icon(name:str) -> QIcon:
    if name not in icon_cache:
        icon_cache[name] = QIcon(str(get(name)))
    return icon_cache[name]


icon_cache: Dict[str, QIcon] = {}
pixmap_cache: Dict[str, QPixmap] = {}

class Icons:
    TreeFolder = "folder-16x16.png"
    TreeVar = "var-16x16.png"
    TreeRpv = "rpv-16x16.png"
    TreeAlias = "alias-16x16.png"
    RedX = "redx-16x16.png"
    GraphAxis = "axis-16x16.png"
    Show = "show-16x16.png"
    Hide = "hide-16x16.png"
