
__all__ = ['Self', 'List', 'Set', 'Dict', 'Union', 'Optional', 'Any', 'cast', 'Iterable', 
           'Sequence', 'Callable', 'TypedDict', 'Literal',
           'TypeVar', 'ParamSpec', 'TYPE_CHECKING']

try:
    from typing import Self
except ImportError:
    try:
        from typing_extensions import Self  # 3.10 and below. setup.py install it if python < 3.10
    except ImportError:
        class Self: # type: ignore
            pass

from typing import List, Set, Dict, Union, Optional, Any, cast, Iterable, Sequence, Callable, TypedDict, Literal, TypeVar, ParamSpec, TYPE_CHECKING
