import os
from scrutiny.gui.core.exceptions import GuiError
from pathlib import Path
from qtpy.QtGui import QPixmap

ASSET_PATH = os.path.dirname(__file__)

def get(name:str) -> Path:
    outpath = os.path.join(ASSET_PATH, name)
    if os.path.commonpath([outpath, ASSET_PATH]) != ASSET_PATH:
        raise GuiError("Directory traversal while reading an asset")
    return Path(outpath)

def logo_icon() -> Path:
    return get('scrutiny-logo-square-64x64.png')

def load_pixmap(name) -> QPixmap:
    return QPixmap(str(get(name)))
