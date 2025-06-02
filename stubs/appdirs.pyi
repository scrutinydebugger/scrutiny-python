#    appdirs.pyi
#        A stub file for the appdirs module
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

from typing import Optional

def user_data_dir(
    appname:Optional[str]=None, 
    appauthor:Optional[str]=None, 
    version:Optional[str]=None, 
    roaming:bool=False
    ) -> str:...

def site_data_dir(
    appname:Optional[str]=None, 
    appauthor:Optional[str]=None, 
    version:Optional[str]=None, 
    multipath:bool=False
    ) -> str:...

def user_config_dir(
    appname:Optional[str]=None, 
    appauthor:Optional[str]=None, 
    version:Optional[str]=None, 
    roaming:bool=False
    ) -> str:...

def site_config_dir(
    appname:Optional[str]=None, 
    appauthor:Optional[str]=None, 
    version:Optional[str]=None, 
    multipath:bool=False
    ) -> str:...

def user_cache_dir(
    appname:Optional[str]=None, 
    appauthor:Optional[str]=None, 
    version:Optional[str]=None, 
    opinion:bool=True
    ) -> str:...

def user_state_dir(
    appname:Optional[str]=None, 
    appauthor:Optional[str]=None, 
    version:Optional[str]=None, 
    roaming:bool=False
    ) -> str:...

def user_log_dir(
    appname:Optional[str]=None, 
    appauthor:Optional[str]=None, 
    version:Optional[str]=None, 
    opinion:bool=True
    ) -> str:...


class AppDirs(object):
    def __init__(self, 
                 appname:Optional[str]=None, 
                 appauthor:Optional[str]=None, 
                 version:Optional[str]=None, 
                 roaming:bool=False, 
                 multipath:bool=False) -> None: ...

    @property
    def user_data_dir(self) -> str: ...
    @property
    def site_data_dir(self) -> str: ...
    @property
    def user_config_dir(self) -> str: ...
    @property
    def site_config_dir(self) -> str: ...
    @property
    def user_cache_dir(self) -> str: ...
    @property
    def user_state_dir(self) -> str: ...
    @property
    def user_log_dir(self) -> str: ...
