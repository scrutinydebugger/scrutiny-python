__all__ = [
    'Throttler',
    'Timer',
    'get_not_none',
    'update_dict_recursive',
    'format_eng_unit',
    'format_sec_to_dhms',
    'format_exception',
    'UnitTestStub',
    'SuppressException',
    'log_exception',
    'MutableInt',
    'MutableFloat',
    'MutableBool',
    'MutableNullableInt',
    'MutableNullableFloat',
    'MutableNullableBool',
    'NullableMutable',
]


import traceback
import types
import logging
import threading
from copy import deepcopy
from dataclasses import dataclass

from scrutiny.tools.throttler import Throttler
from scrutiny.tools.timer import Timer
from scrutiny.tools.typing import *

T=TypeVar("T")

def get_not_none(v:Optional[T]) -> T:
    assert v is not None
    return v

def get_default_val(v:Optional[T], default:T) -> T:
    if v is None:
        return default
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

def format_sec_to_dhms(sec:int) -> str:
    if sec < 60:
        outstr = f"{sec}s"
    else:
        minutes = int(sec//60)
        sec -= minutes*60
        if minutes < 60:
            outstr = f"{minutes}m{sec}s"
        else:
            hour = int(minutes //60)
            minutes -= hour*60
            if hour < 24:
                outstr = f"{hour}h{minutes}m{sec}s"
            else:
                days = int(hour//24)
                hour -= days*24
                outstr = f"{days}d {hour}h{minutes}m{sec}s"
    
    return outstr

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
    suppress_exception:bool
    exception_logged:bool

    def __init__(self, 
                 logger:logging.Logger, 
                 exc:Union[List[Type[BaseException]], Type[BaseException]],
                 msg:Optional[str] = None,
                 str_level:Optional[int]=logging.ERROR, 
                 traceback_level:Optional[int]=logging.DEBUG,
                 suppress_exception:bool = False) -> None:
        self.logger = logger
        self.str_level = str_level
        self.traceback_level = traceback_level
        self.msg = msg
        self.suppress_exception = suppress_exception
        self.exception_logged = False
        if not isinstance(exc, list):
            exc = [exc]
        self.exc = exc

    def __enter__(self) -> "LogException":
        return self
    
    def __exit__(self, 
                 exc_type: Optional[Type[BaseException]], 
                 exc_val: Optional[BaseException], 
                 exc_tb: Optional[types.TracebackType]) -> bool:
        if exc_val is not None and exc_type is not None:
            process = False
            for supported_exc_type in self.exc:
                if exc_type == supported_exc_type or issubclass(exc_type, supported_exc_type):
                    process = True
            if process:
                log_exception(self.logger, exc_val, self.msg, self.str_level, self.traceback_level)
                self.exception_logged=True
                return True if self.suppress_exception else False
            
        return False

class ThreadSyncer(Generic[T]):
    finished:threading.Event
    exception:Optional[Exception]
    return_val:Optional[T]

    def __init__(self) -> None:
        self.finished = threading.Event()
        self.exception = None
        self.return_val = None
    
    def executor_func(self, fn:Callable[..., T]) -> Callable[[], None]:
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

@dataclass
class MutableInt:
    """Helper to pass a int by reference"""
    val:int

@dataclass
class MutableNullableInt:
    """Helper to pass an Optional[int] by reference"""
    val:Optional[int]

@dataclass
class MutableFloat:
    """Helper to pass a float by reference"""
    val:float

@dataclass
class MutableNullableFloat:
    """Helper to pass an Optional[float] by reference"""
    val:Optional[float]

@dataclass
class MutableBool:
    """Helper to pass a bool by reference"""
    val:bool

    def set(self) -> None:
        self.val = True
    
    def clear(self) -> None:
        self.val = False

    def toggle(self) -> None:
        self.val = not self.val

    def __eq__(self, other:Any) -> bool:
        if isinstance(other, bool):
            return self.val == other
        if isinstance(other, MutableBool):
            return self.val == other.val
        return False
    
    def __bool__(self) -> bool:
        return self.val

@dataclass
class MutableNullableBool:
    """Helper to pass an Optional[bool] by reference"""
    val:Optional[bool]

class NullableMutable(Generic[T]):
    val:Optional[T]
    def __init__(self, val:Optional[T]) -> None:
        self.val = val
    
