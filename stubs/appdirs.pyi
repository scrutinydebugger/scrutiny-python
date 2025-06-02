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
