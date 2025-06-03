#    persistent_data.py
#        A collection of GUI-wide dictionaries that are persistent across process execution.
#        Organized by namespaces
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['AppPersistentData', 'MainAppPersistentDataManager']

from pathlib import Path
import os
import json
import logging
from scrutiny import tools
from scrutiny.tools import validation
from scrutiny.gui.globals import get_gui_storage

from scrutiny.tools.typing import *

SAVABLE_VAL_TYPE = Union[str, int, bool, float, None, List[str], List[int], List[bool], List[float]]
GLOBAL_NAMESPACE = 'global'


class AppPersistentData:
    _namespace_name: str
    _valdict: Dict[str, SAVABLE_VAL_TYPE]

    class CommonKeys:
        LastSaveDir = 'last_save_dir'
        LongDateFormat = 'long_date_format'

    def __init__(self, namespace_name: str) -> None:
        self._namespace_name = namespace_name
        self._valdict = {}

    def get_workdir(self) -> Path:
        return Path(os.getcwd())

    def get_last_save_dir_or_workdir(self) -> Path:
        dirstr = self.get(self.CommonKeys.LastSaveDir)
        if not isinstance(dirstr, str) or not os.path.isdir(dirstr):
            return self.get_workdir()
        return Path(dirstr)

    def set_last_save_dir(self, d: Path) -> None:
        if d.exists():
            self.set(self.CommonKeys.LastSaveDir, str(d))

    def long_datetime_format(self) -> str:
        return self.get_str(self.CommonKeys.LongDateFormat, r'%Y-%m-%d %H:%M:%S')

    def clear(self) -> None:
        self._valdict.clear()

    def prune(self, allowed_keys: Sequence[str]) -> None:
        for key in list(self._valdict.keys()):
            if key not in allowed_keys:
                del self._valdict[key]

    def get(self, key: str, default: SAVABLE_VAL_TYPE = None) -> SAVABLE_VAL_TYPE:
        return self._valdict.get(key, default)

    def get_str(self, key: str, default: str) -> str:
        val = self.get(key)
        if not isinstance(val, str):
            return default
        return val

    def get_bool(self, key: str, default: bool) -> bool:
        val = self.get(key)
        if not isinstance(val, (int, bool)):
            return default
        return bool(val)

    def get_float(self, key: str, default: float) -> float:
        val = self.get(key)
        if not isinstance(val, (int, float)):
            return default
        return float(val)

    def get_int(self, key: str, default: int) -> int:
        val = self.get(key)
        if not isinstance(val, int):
            return default
        return int(val)

    def get_list_str(self, key: str, default: List[str]) -> List[str]:
        val = self.get(key)
        if not isinstance(val, list):
            return default
        return [v for v in val if isinstance(v, str)]   # Silently drop bad values

    def set_if_not_str(self, key: str, default: str) -> None:
        v = self.get(key)
        if not isinstance(v, str):
            self.set(key, default)

    def set(self, key: str, val: SAVABLE_VAL_TYPE) -> None:
        validation.assert_type(key, 'key', str)
        validation.assert_type(val, 'val', (str, int, float, bool, type(None), list))
        if isinstance(val, list) and len(val) > 0:  # Enforce list of same type. No mix
            type0 = type(val[0])
            validation.assert_type(val[0], 'val[0]', (str, int, float, bool, type(None)))
            for v in val:
                validation.assert_type(v, 'val[N]', type0)

        self._valdict[key] = val

    def set_list_str(self, key: str, val: List[str]) -> None:
        validation.assert_type(val, 'val', list)
        for v in val:
            validation.assert_type(v, 'val[N]', str)
        self.set(key, val)

    def set_str(self, key: str, val: str) -> None:
        validation.assert_type(val, 'val', str)
        self.set(key, val)

    def set_float(self, key: str, val: float) -> None:
        validation.assert_type(val, 'val', (float, int))
        self.set(key, float(val))

    def set_int(self, key: str, val: int) -> None:
        validation.assert_type(val, 'val', int)
        self.set(key, int(val))

    def set_bool(self, key: str, val: bool) -> None:
        validation.assert_type(val, 'val', bool)
        self.set(key, bool(val))

    def to_dict(self) -> Dict[str, SAVABLE_VAL_TYPE]:
        return self._valdict.copy()

    def update_from_dict(self, val: Dict[str, SAVABLE_VAL_TYPE]) -> None:
        return self._valdict.update(val)


class AppPersistentDataManager:
    FILENAME = 'persistent_data.json'
    _namespaces: Dict[str, AppPersistentData]
    _logger: logging.Logger
    _storage_folder: Path

    _global_instance: Optional["AppPersistentDataManager"] = None

    @classmethod
    def get(cls) -> "AppPersistentDataManager":
        if cls._global_instance is None:
            cls._global_instance = cls(get_gui_storage())
        return cls._global_instance

    def __init__(self, storage_folder: Path) -> None:

        self._logger = logging.getLogger(self.__class__.__name__)
        self._namespaces = {}
        self._storage_folder = storage_folder
        self.global_namespace()  # Create it if not exist

        file = self.get_storage_file()
        if os.path.isfile(file):
            try:
                with open(file, 'r') as f:
                    content = json.load(f)

                assert isinstance(content, dict)
                for namespace_name, data_dict in content.items():
                    assert isinstance(namespace_name, str)
                    assert isinstance(data_dict, dict)

                    if namespace_name not in self._namespaces:
                        self._namespaces[namespace_name] = AppPersistentData(namespace_name)
                    self._namespaces[namespace_name].update_from_dict(data_dict)

            except (json.JSONDecodeError, AssertionError, FileNotFoundError) as e:
                tools.log_exception(self._logger, e, "Could not load GUI persistent data")
                with tools.SuppressException():
                    os.remove(file)

        self.save()

    def save(self) -> None:
        """Saves the persistent data to a .json file. Each namespace present a subdict in the file"""
        file = self.get_storage_file()
        with tools.SuppressException():
            os.makedirs(file.parent, exist_ok=True)

        try:
            with open(file, 'w') as f:
                dout: Dict[str, Dict[str, SAVABLE_VAL_TYPE]] = {}
                for namespace_name in self._namespaces:
                    dtemp = self._namespaces[namespace_name].to_dict()
                    try:
                        json.dumps(dtemp)
                    except Exception as e:
                        tools.log_exception(self._logger, e, f"Invalid persistent data for namespace {namespace_name}")
                        dtemp = {}  # Clear it
                    if len(dtemp) > 0:
                        dout[namespace_name] = dtemp
                json.dump(dout, f, indent=4, sort_keys=True)
        except Exception as e:
            tools.log_exception(self._logger, e, "Could not save GUI persistent data")
            with tools.SuppressException():
                os.remove(file)

    def get_storage_file(self) -> Path:
        return self._storage_folder / self.FILENAME

    def get_namespace(self, name: str) -> AppPersistentData:
        """Load or create a namespace"""
        if name not in self._namespaces:
            self._namespaces[name] = AppPersistentData(name)
        return self._namespaces[name]

    def global_namespace(self) -> AppPersistentData:
        """Return the global namespace"""
        return self.get_namespace(GLOBAL_NAMESPACE)


gui_persistent_data = AppPersistentDataManager(get_gui_storage())
