__all__ = [
    'Throttler',
    'Timer'
]
from .throttler import Throttler
from .timer import Timer

from copy import deepcopy
from typing import Dict, Any

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
