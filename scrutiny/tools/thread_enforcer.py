#    thread_enforcer.py
#        A runtime checker that enforces the thread ID of function caller. Prevents race conditions
#        from misusage of internal APIs
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import threading
from typing import Optional, Dict, Set, Callable, Any, TypeVar

class ThreadValidationError(Exception):
    pass

class ThreadEnforcer:
    _thread_to_name_map:Dict[int, Set[str]] = {}

    @classmethod
    def register_thread(cls, name:str, thread_id:Optional[int]=None, unique:bool=False) -> None:
        if unique:
            for nameset in cls._thread_to_name_map.values():
                if name in nameset:
                    raise ThreadValidationError(f"More than 1 instance of thread {name}")
        
        if thread_id is None:
            thread_id = threading.get_ident()
    
        if thread_id not in cls._thread_to_name_map:
            cls._thread_to_name_map[thread_id] = set()
                
        cls._thread_to_name_map[thread_id].add(name)
    
    @classmethod
    def unregister_thread(cls, name:str, thread_id:Optional[int]=None) -> None:
        if thread_id is None:
            thread_id = threading.get_ident()
        
        if thread_id not in cls._thread_to_name_map:
            raise ThreadValidationError(f"Thread ID {thread_id} is not registered")
        
        if name not in cls._thread_to_name_map[thread_id]:
            raise ThreadValidationError(f"Thread ID {thread_id} is not registered under the name {name}")

        cls._thread_to_name_map[thread_id].remove(name)
    
    @classmethod
    def assert_thread(cls, name:str) -> None:
        thread_id = threading.get_ident()
        if thread_id not in cls._thread_to_name_map:
            raise ThreadValidationError(f"Running from unknown thread. Expected {name}")
        
        thread_name_set = cls._thread_to_name_map[thread_id]
        if name not in thread_name_set:
            raise ThreadValidationError(f"Not running from thread {name}. Actual thread ID ({thread_id}) is associated with these names : {thread_name_set})")

T = TypeVar('T')

def enforce_thread(name:str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def decorator(function:Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args:Any, **kwargs:Any) -> T:
            ThreadEnforcer.assert_thread(name)
            result = function(*args, **kwargs)
            return result
        return wrapper
    return decorator

def thread_func(name:str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def decorator(function:Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args:Any, **kwargs:Any) ->  T:
            ThreadEnforcer.register_thread(name, unique=True)
            try:
                result = function(*args, **kwargs)
            finally:
                ThreadEnforcer.unregister_thread(name)
            return result
        return wrapper
    return decorator

def register_thread(name:str, thread_id:Optional[int]=None, unique:bool=False) -> None:
    ThreadEnforcer.register_thread(name, thread_id, unique)

def unregister_thread(name:str, thread_id:Optional[int]=None) -> None:
    ThreadEnforcer.unregister_thread(name, thread_id)
