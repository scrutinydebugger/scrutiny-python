import appdirs  # type: ignore
from pathlib import Path

GUI_STORAGE = Path(appdirs.user_data_dir(appname='gui', appauthor='scrutiny'))

def get_gui_storage() -> Path:
    return GUI_STORAGE
