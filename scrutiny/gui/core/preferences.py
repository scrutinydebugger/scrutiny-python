#    preferences.py
#        An interface to the user preferences
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['gui_preferences', 'AppPreferences']

from pathlib import Path
import os

from typing import Optional, Dict

DEFAULT_FACILITY = 'default'

class AppPreferences:
    _facility_name:str
    _last_save_dir:Optional[Path]

    def __init__(self, facility_name:str) -> None:
        self._facility_name = facility_name
        self._last_save_dir = None

    def get_workdir(self) -> Path:
        return Path(os.getcwd())
    
    def get_last_save_dir_or_workdir(self) -> Path:
        if self._last_save_dir is not None:
            if self._last_save_dir.exists():
                return self._last_save_dir 
        return self.get_workdir()
    
    def set_last_save_dir(self, d:Path) -> None:
        if d.exists():
            self._last_save_dir = d

    def long_datetime_format(self) -> str:
        return r'%Y-%m-%d %H:%M:%s'

class PreferenceHandle:
    _preferences:Dict[str, AppPreferences]

    def __init__(self) -> None:
        self._preferences = {}
        self.default()  # Create it if not exist
        # TODO : Load from user temp folder

    def facility(self, name:str) -> AppPreferences:
        if name not in self._preferences:
            self._preferences[name] = AppPreferences(name)
        return self._preferences[name]
    
    def default(self) -> AppPreferences:
        return self.facility(DEFAULT_FACILITY)
    

gui_preferences = PreferenceHandle()
