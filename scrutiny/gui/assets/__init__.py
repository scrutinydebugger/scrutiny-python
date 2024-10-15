import os
from scrutiny.gui.core.exceptions import GuiError
from pathlib import Path
from qtpy.QtGui import QPixmap

from typing import List, Union

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
    return QPixmap(str(get(name)))

