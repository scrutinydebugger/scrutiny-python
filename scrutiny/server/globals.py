import appdirs  # type: ignore
from pathlib import Path

from typing import Union
SERVER_STORAGE = Path(appdirs.user_data_dir(appname='server', appauthor='scrutiny'))

def set_server_storage(val:Union[Path]) -> None:
    global SERVER_STORAGE
    SERVER_STORAGE = val

def get_server_storage() -> Path:
    return SERVER_STORAGE
