__all__ = [
    'Throttler',
    'Timer',
    'get_not_none',
    'update_dict_recursive',
    'format_eng_unit',
    'format_exception',
    'UnitTestStub',
    'SuppressException',
    'log_exception'
]

from .throttler import Throttler
from .timer import Timer

import traceback
from copy import deepcopy
from typing import Dict, Any, Optional, TypeVar, List, Tuple, Type, cast, Union, Callable, Generic
import types
import logging
from dataclasses import dataclass
import threading

T=TypeVar("T")

def get_not_none(v:Optional[T]) -> T:
    assert v is not None
    return v

def copy_type(f: T) -> Callable[[Any], T]:
    return lambda x: x

def update_dict_recursive(d1:Dict[Any, Any], d2:Dict[Any, Any]) -> None:
    if not isinstance(d1, dict):
        raise ValueError("Cannot merge non-dictionnaries")
    if not isinstance(d2, dict):
        raise ValueError("Cannot merge non-dictionnaries")
    
    for k in d2.keys():
        if isinstance(d2[k], dict):
            if k not in d1:
                d1[k] = {}
            if isinstance(d1[k], dict):
                update_dict_recursive(d1[k], d2[k])
            else:
                # We're losing a value here
                d1[k] = deepcopy(d2[k])
        else:
            d1[k] = deepcopy(d2[k])

def format_eng_unit(val:float, decimal:int=0, unit:str="", binary:bool=False) -> str:
    assert decimal >= 0
    format_string = f"%0.{decimal}f"
    if val == 0:    # Special case to avoid writing : 0piB instead of 0B
        return (format_string % val) + unit 
    
    prefixes:List[Tuple[float, str]]
    if binary:      
        prefixes = [
            (1/(1024*1024*1024*1024), "pi"),
            (1/(1024*1024*1024), "ni"),
            (1/(1024*1024), "ui"),
            (1/1024, "mi"),
            (1, ""),
            (1024, "Ki"),
            (1024*1024, "Mi"),
            (1024*1024*1024, "Gi"),
            (1024*1024*1024*1024, "Ti"),
        ]
    else:
        prefixes = [
            (1/(1000*1000*1000*1000), "p"),
            (1/(1000*1000*1000), "n"),
            (1/(1000*1000), "u"),
            (1/1000, "m"),
            (1, ""),
            (1000, "K"),
            (1000*1000, "M"),
            (1000*1000*1000, "G"),
            (1000*1000*1000*1000, "T"),
        ]
    
    base: Optional[float] = None
    prefix: Optional[str] = None
    for i in range(len(prefixes)):
        if i < len(prefixes)-1:
            next_base, _ = prefixes[i+1]
            if val < next_base:
                base, prefix = prefixes[i]
                break
        else:
            base, prefix = prefixes[i]

    assert base is not None
    assert prefix is not None

    val = round(val / base, decimal)
    return (format_string % val) + prefix + unit 


def format_exception(e:BaseException) -> str:
    return ''.join(traceback.format_exception(type(e), e, e.__traceback__))

class UnitTestStub:
    pass


class SuppressException:
    ignore_types:List[Type[BaseException]]

    def __init__(self, *args:Any) -> None:
        self.ignore_types = [] 
        for arg in args:
            self.ignore_types.append(cast(Type[BaseException], arg))
        if len(args) == 0:
            self.ignore_types.append(Exception)
    
    def __enter__(self) -> "SuppressException":
        return self

    def __exit__(self, 
                 exc_type: Optional[Type[BaseException]], 
                 exc_val: Optional[BaseException], 
                 exc_tb: Optional[types.TracebackType]) -> bool:
        if exc_type is not None: 
            for exc_type in self.ignore_types:
                if isinstance(exc_val, exc_type):
                    return True
        return False


def log_exception(logger:logging.Logger,
            exc:BaseException,
            msg:Optional[str] = None,
            str_level:Optional[int]=logging.ERROR, 
            traceback_level:Optional[int]=logging.DEBUG) -> None:
    if str_level is not None:
        if logger.isEnabledFor(str_level):
            if msg is not None:
                error_str = f"{msg}\n  Underlying error: {exc}"
            else:
                error_str = str(exc)
            logger.log(str_level, error_str)
    
    if traceback_level is not None:
        if logger.isEnabledFor(traceback_level):
            logger.log(traceback_level, format_exception(exc))

class LogException:
    logger:logging.Logger
    str_level:Optional[int]
    traceback_level:Optional[int]
    exc:List[Type[BaseException]]

    def __init__(self, 
                 logger:logging.Logger, 
                 exc:Union[List[Type[BaseException]], Type[BaseException]],
                 msg:Optional[str] = None,
                 str_level:Optional[int]=logging.ERROR, 
                 traceback_level:Optional[int]=logging.DEBUG) -> None:
        self.logger = logger
        self.str_level = str_level
        self.traceback_level = traceback_level
        self.msg = msg
        if not isinstance(exc, list):
            exc = [exc]
        self.exc = exc

    def __enter__(self) -> "LogException":
        return self
    
    def __exit__(self, 
                 exc_type: Optional[Type[BaseException]], 
                 exc_val: Optional[BaseException], 
                 exc_tb: Optional[types.TracebackType]) -> bool:
        if exc_val is not None:
            if exc_type in self.exc:
                log_exception(self.logger, exc_val, self.msg, self.str_level, self.traceback_level)
                return True
            
        return False

class ThreadSyncer(Generic[T]):
    finished:threading.Event
    exception:Optional[Exception]
    return_val:Optional[T]

    def __init__(self) -> None:
        self.finished = threading.Event()
        self.exception = None
        self.return_val = None
    
    def executor_func(self, fn:Callable[..., T]) -> Callable[..., None]:
        def wrapper() -> None:
            try:
                self.return_val = fn()
            except Exception as e:
                self.exception = e
            finally:
                self.finished.set()
        return wrapper


def run_in_thread(fn:Callable[..., T], sync_var:Optional[ThreadSyncer[T]]=None) -> None:
    fn2 = fn if sync_var is None else sync_var.executor_func(fn)
    thread = threading.Thread(target = fn2, daemon=True)
    thread.start()
