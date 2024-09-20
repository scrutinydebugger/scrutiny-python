import os
from scrutiny.gui.exceptions import GuiError

ASSET_PATH = os.path.dirname(__file__)

def get(name:str) -> str:
    outpath = os.path.join(ASSET_PATH, name)
    if os.path.commonpath([outpath, ASSET_PATH]) != ASSET_PATH:
        raise GuiError("Directory traversal while reading an asset")
    return outpath

def icon() -> str:
    return get('scrutiny-logo-square-64x64.png')