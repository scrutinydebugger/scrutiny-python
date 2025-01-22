__all__ = [
    'get',
    'load_bin',
    'load_text',
    'load_pixmap',
    'IconSet',
    'IconFormat',
    'icon_filename',
    'Icons',
    'load_icon',
    'load_icon_filename',
    'load_tiny_icon',
    'load_medium_icon',
    'load_large_icon',
]

import os
from scrutiny.gui.core.exceptions import GuiError
from pathlib import Path
from PySide6.QtGui import QPixmap, QIcon

from typing import List, Union, Dict
import enum

ASSET_PATH = os.path.dirname(__file__)


def get(name:Union[str, Path, List[str]]) -> Path:
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

def load_pixmap(name:Union[str, Path]) -> QPixmap:
    if isinstance(name, Path):
        name = str(name)
    if name not in pixmap_cache:
        pixmap_cache[name] = QPixmap(str(get(name)))
    return pixmap_cache[name]

def load_icon_file(name:Union[str, Path]) -> QIcon:
    if isinstance(name, Path):
        name = str(name)
    if name not in icon_cache:
        icon_cache[name] = QIcon(str(get(name)))
    return icon_cache[name]


icon_cache: Dict[str, QIcon] = {}
pixmap_cache: Dict[str, QPixmap] = {}

class IconSet(enum.Enum):
    Default = 'default'

class IconFormat(enum.Enum):
    Tiny = enum.auto()
    Medium = enum.auto()
    Large = enum.auto()

class Icons(enum.Enum):
    Folder = "folder"
    Var = "var"
    Rpv = "rpv"
    Alias = "alias"
    RedX = "redx"
    GraphAxis = "axis"
    Eye = "eye"
    EyeBar = "eye-bar"
    Image = "image"
    CSV = "csv"
    Warning = "warning"
    Error = "error"
    Info = "info"
    GraphCursor = "graph-cursor"
    GraphNoCursor = "graph-no-cursor"
    ZoomX = "zoom-x"
    ZoomY = "zoom-y"
    ZoomXY = "zoom-xy"
    Zoom100 = "zoom-100"
    SquareRed = "square-red"
    SquareYellow = "square-yellow"
    SquareGreen = "square-green"
    ScrutinyLogo = "scrutiny-logo"
    Download = "download"

def icon_filename(name:Icons, format:IconFormat, iconset:IconSet=IconSet.Default) -> Path:
    possible_formats = {
        IconFormat.Tiny : [
            (16,16),
            (16,12)
        ],
        IconFormat.Medium : [
            (64,64),
            (64,48)
        ],
        IconFormat.Large : [
            (256,256),
            (256,192)
        ]
    }

    for f in possible_formats[format]:
        candidate = get(['icons', iconset.value, f"{name.value}_{f[0]}x{f[1]}.png"])
        if os.path.isfile(candidate):
            return candidate

    raise FileNotFoundError(f"Could not find an icon candidate for {name.name}({name.value}) with format {format.name} in icon set {iconset.name}")


def load_icon(name:Icons, format:IconFormat, iconset:IconSet=IconSet.Default) -> QIcon:
    return load_icon_file(icon_filename(name, format, iconset))

def load_tiny_icon(name:Icons, iconset:IconSet=IconSet.Default) -> QIcon:
    return load_icon_file(icon_filename(name, IconFormat.Tiny, iconset))

def load_medium_icon(name:Icons, iconset:IconSet=IconSet.Default) -> QIcon:
    return load_icon_file(icon_filename(name, IconFormat.Medium, iconset))

def load_large_icon(name:Icons, iconset:IconSet=IconSet.Default) -> QIcon:
    return load_icon_file(icon_filename(name, IconFormat.Large, iconset))

def load_tiny_icon_as_pixmap(name:Icons, iconset:IconSet=IconSet.Default) -> QPixmap:
    return load_pixmap(icon_filename(name, IconFormat.Tiny, iconset))

def load_medium_icon_as_pixmap(name:Icons, iconset:IconSet=IconSet.Default) -> QPixmap:
    return load_pixmap(icon_filename(name, IconFormat.Medium, iconset))

def load_large_icon_as_pixmap(name:Icons, iconset:IconSet=IconSet.Default) -> QPixmap:
    return load_pixmap(icon_filename(name, IconFormat.Large, iconset))
