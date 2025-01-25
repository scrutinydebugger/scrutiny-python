#    preferences.py
#        An interface to the user preferences
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['AppPreferences', 'MainAppPreferenceManager']

from pathlib import Path
import os
import json
import logging
from scrutiny import tools
from scrutiny.tools import validation
from scrutiny.gui.globals import get_gui_storage

import typing
from scrutiny.tools.typing import *

PREFERENCE_VAL_TYPE = Union[str, int, bool, float, None]
GLOBAL_NAMESPACE = 'global'


class AppPreferences:
    _namespace_name:str
    _valdict:Dict[str, PREFERENCE_VAL_TYPE]

    class CommonKeys:
        LastSaveDir = 'last_save_dir'
        LongDateFormat = 'long_date_format'

    def __init__(self, namespace_name:str) -> None:
        self._namespace_name = namespace_name
        self._valdict = {}

    def get_workdir(self) -> Path:
        return Path(os.getcwd())
    
    def get_last_save_dir_or_workdir(self) -> Path:
        dirstr = self.get(self.CommonKeys.LastSaveDir)
        if not isinstance(dirstr, str) or not os.path.isdir(dirstr):
            return self.get_workdir()
        return Path(dirstr)
    
    def set_last_save_dir(self, d:Path) -> None:
        if d.exists():
            self.set(self.CommonKeys.LastSaveDir, str(d))

    def long_datetime_format(self) -> str:
        return self.get_str(self.CommonKeys.LongDateFormat, r'%Y-%m-%d %H:%M:%S')

    def clear(self) -> None:
        self._valdict.clear()

    def prune(self, allowed_keys:Sequence[str]) -> None:
        for key in list(self._valdict.keys()):
            if key not in allowed_keys:
                del self._valdict[key]

    def get(self, key:str, default:PREFERENCE_VAL_TYPE = None) -> PREFERENCE_VAL_TYPE:
        return self._valdict.get(key, default)
    
    def get_str(self, key:str, default:str) -> str:
        val = self.get(key)
        if not isinstance(val, str):
            return default
        return val
    
    def get_bool(self, key:str, default:bool) -> bool:
        val = self.get(key)
        if not isinstance(val, (int, bool)):
            return default
        return bool(val)
    
    def get_float(self, key:str, default:float) -> float:
        val = self.get(key)
        if not isinstance(val, (int, float)):
            return default
        return float(val)
    
    def get_int(self, key:str, default:int) -> int:
        val = self.get(key)
        if not isinstance(val, int):
            return default
        return int(val)
    
    def set_if_not_str(self, key:str, default:str) -> None:
        v = self.get(key)
        if not isinstance(v, str):
            self.set(key, default)


    def set(self, key:str, val:PREFERENCE_VAL_TYPE) -> None:
        validation.assert_type(key, 'key', str)
        validation.assert_type(val, 'val', (typing.get_args(PREFERENCE_VAL_TYPE)))
        self._valdict[key] = val
    
    def set_str(self, key:str, val:str) -> None:
        validation.assert_type(val, 'val', str)
        self.set(key, val)
    
    def set_float(self, key:str, val:float) -> None:
        validation.assert_type(val, 'val', (float, int))
        self.set(key, float(val))

    def set_int(self, key:str, val:int) -> None:
        validation.assert_type(val, 'val', int)
        self.set(key, int(val))
    
    def set_bool(self, key:str, val:bool) -> None:
        validation.assert_type(val, 'val', bool)
        self.set(key, bool(val))

    def to_dict(self) -> Dict[str, PREFERENCE_VAL_TYPE]:
        return self._valdict.copy()
    
    def update_from_dict(self, val:Dict[str, PREFERENCE_VAL_TYPE]) -> None:
        return self._valdict.update(val)

class AppPreferenceManager:
    FILENAME = 'preferences.json'
    _namespaces:Dict[str, AppPreferences]
    _logger:logging.Logger
    _storage_folder:Path

    _global_instance:Optional["AppPreferenceManager"] = None

    @classmethod
    def get(cls) -> "AppPreferenceManager":
        if cls._global_instance is None:
            cls._global_instance = cls(get_gui_storage())
        return cls._global_instance
    
    def __init__(self, storage_folder:Path) -> None: 

        self._logger = logging.getLogger(self.__class__.__name__)
        self._namespaces = {}
        self._storage_folder = storage_folder
        self.global_namespace()  # Create it if not exist
        
        file = self.get_preferences_file()
        if os.path.isfile(file):
            try:
                with open(file, 'r') as f:
                    content = json.load(f)
                
                assert isinstance(content, dict)
                for namespace_name, preference_dict in content.items():
                    assert isinstance(namespace_name, str)
                    assert isinstance(preference_dict, dict)
                    
                    if namespace_name not in self._namespaces:
                        self._namespaces[namespace_name] = AppPreferences(namespace_name)
                    self._namespaces[namespace_name].update_from_dict(preference_dict)

            except (json.JSONDecodeError, AssertionError, FileNotFoundError ) as e:
                tools.log_exception(self._logger, e, "Could not load GUI preferences")
                with tools.SuppressException():
                    os.remove(file)
        
        self.save()
    
    def save(self) -> None:
        file = self.get_preferences_file()
        with tools.SuppressException():
            os.makedirs(file.parent, exist_ok=True)
        
        try:
            with open(file, 'w') as f:
                dout:Dict[str, Dict[str, PREFERENCE_VAL_TYPE]] = {}
                for namespace_name in self._namespaces:
                    dtemp = self._namespaces[namespace_name].to_dict()
                    try:
                        json.dumps(dtemp)
                    except Exception as e:
                        tools.log_exception(self._logger, e, f"Invalid preferences for namespace {namespace_name}")
                        dtemp = {}  # Clear it
                    dout[namespace_name] = dtemp
                json.dump(dout, f, indent=4, sort_keys=True)
        except Exception as e:
            tools.log_exception(self._logger, e, "Could not save GUI preferences")
            with tools.SuppressException():
                os.remove(file)

    def get_preferences_file(self) -> Path:
        return self._storage_folder / self.FILENAME

    def get_namespace(self, name:str) -> AppPreferences:
        if name not in self._namespaces:
            self._namespaces[name] = AppPreferences(name)
        return self._namespaces[name]
    
    def global_namespace(self) -> AppPreferences:
        return self.get_namespace(GLOBAL_NAMESPACE)


gui_preferences = AppPreferenceManager(get_gui_storage())
