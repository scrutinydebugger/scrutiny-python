#    validation.py
#        Helpers to validate variables types and values
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2023 Scrutiny Debugger

__all__ = [
    'assert_type',
    'assert_type_or_none',
    'assert_val_in',
    'assert_int_range',
    'assert_int_range_if_not_none',
    'assert_float_range',
    'assert_float_range_if_not_none',
    'assert_is_iterable',
    'assert_not_none',
    'assert_dict_key'
]

import math
from scrutiny.tools.typing import *


def assert_type(var: Any, name: str, types: Union[Type[Any], List[Type[Any]], Tuple[Type[Any], ...]]) -> None:
    if isinstance(types, (list, tuple)):
        typenames: List[str] = [x.__name__ for x in types]
        bad_val = not isinstance(var, tuple(types))
        if int in types and bool not in types:
            bad_val |= isinstance(var, bool)    # bools are valid int

        if bad_val:
            raise TypeError(f"\"{name}\" type is not one of \"{typenames}\". Got \"{var.__class__.__name__}\" instead")
    else:
        bad_val = not isinstance(var, types)
        if types == int:
            bad_val |= isinstance(var, bool)    # bools are valid int

        if bad_val:
            raise TypeError(f"\"{name}\" is not of type \"{types.__name__}\". Got \"{var.__class__.__name__}\" instead")


def assert_type_or_none(var: Any, name: str, types: Union[Type[Any], List[Type[Any]], Tuple[Type[Any], ...]]) -> None:
    if isinstance(types, type):
        types = [types]
    else:
        types = list(types)
    types.append(type(None))
    assert_type(var, name, types)


def assert_val_in(var: Any, name: str, vals: Sequence[Any]) -> None:
    if var not in vals:
        raise ValueError(f"\"{name}\" has an invalid value. Expected one of {vals}")


def assert_int_range(val: int, name: str, minval: Optional[int] = None, maxval: Optional[int] = None) -> int:
    assert_type(val, name, int)
    if minval is not None:
        if val < minval:
            raise ValueError(f"{name} must be greater than {minval}. Got {val}")

    if maxval is not None:
        if val > maxval:
            raise ValueError(f"{name} must be less than {maxval}. Got {val}")
    return val


def assert_int_range_if_not_none(val: Optional[int], name: str, minval: Optional[int] = None, maxval: Optional[int] = None) -> Optional[int]:
    if val is None:
        return None
    return assert_int_range(val, name, minval, maxval)


def assert_float_range(val: Union[int, float], name: str, minval: Optional[float] = None, maxval: Optional[float] = None) -> float:
    if isinstance(val, int) and not isinstance(val, bool):
        val = float(val)
    assert_type(val, name, float)

    if not math.isfinite(val):
        raise ValueError(f"{name} is invalid. Got {val}")

    if minval is not None:
        if val < minval:
            raise ValueError(f"{name} must be greater than {minval}. Got {val}")

    if maxval is not None:
        if val > maxval:
            raise ValueError(f"{name} must be less than {maxval}. Got {val}")
    return val


def assert_float_range_if_not_none(val: Optional[float], name: str, minval: Optional[float] = None, maxval: Optional[float] = None) -> Optional[float]:
    if val is None:
        return None
    return assert_float_range(val, name, minval, maxval)


def assert_is_iterable(val: Any, name: str) -> None:
    try:
        iter(val)
    except TypeError:
        raise ValueError(f"{name} is not iterable. Got type: {val.__class__.__name__}")


def assert_not_none(val: Any, name: str) -> None:
    if val is None:
        raise ValueError(f"{name} is None")


def assert_dict_key(d: Any, name: str, types: Union[Type[Any], Iterable[Type[Any]]], previous_parts: str = '') -> None:
    if isinstance(types, type):
        types = tuple([types])
    else:
        types = tuple(types)

    parts = name.split('.')
    key = parts[0]

    if not key:
        return

    if previous_parts:
        part_name = f"{previous_parts}.{key}"
    else:
        part_name = key
    next_parts = parts[1:]

    if key not in d:
        raise KeyError(f'Missing field "{part_name}"')

    if len(next_parts) > 0:
        if not isinstance(d, dict):
            raise KeyError(f'Field {part_name} is expected to be a dictionary')

        assert_dict_key(d[key], '.'.join(next_parts), types, part_name)
    else:
        isbool = d[key].__class__ == True.__class__  # bool are ints for Python. Avoid allowing bools as valid int.
        if not isinstance(d[key], types) or isbool and bool not in types:
            gotten_type = d[key].__class__.__name__
            typename = "(%s)" % ', '.join([t.__name__ for t in types])
            raise TypeError(f'Field {part_name} is expected to be of type "{typename}" but found "{gotten_type}"')
