__all__ = [
    'Throttler',
    'Timer',
    'get_not_none',
    'update_dict_recursive',
    'format_eng_unit',
    'format_exception',
    'UnitTestStub'
]

from .throttler import Throttler
from .timer import Timer

import traceback
from copy import deepcopy
from typing import Dict, Any, Optional, TypeVar, List, Tuple

T=TypeVar("T")

def get_not_none(v:Optional[T]) -> T:
    assert v is not None
    return v

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


def format_exception(e:Exception) -> str:
    return ''.join(traceback.format_exception(type(e), e, e.__traceback__))

class UnitTestStub:
    pass
