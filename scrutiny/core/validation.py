#    validation.py
#        Helper function for argument validation
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from typing import Union, Any, Type, List, Tuple, Sequence, Optional
import math


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


def assert_val_in(var: Any, name: str, vals: Sequence[Any]) -> None:
    if var not in vals:
        raise ValueError(f"\"{name}\" has an invalid value. Expected one of {vals}")


def assert_int_range(val: int, name: str, minval: Optional[int] = None, maxval: Optional[int] = None) -> None:
    assert_type(val, name, int)
    if minval is not None:
        if val < minval:
            raise ValueError(f"{name} must be greater than {minval}. Got {val}")

    if maxval is not None:
        if val > maxval:
            raise ValueError(f"{name} must be less than {maxval}. Got {val}")


def assert_int_range_if_not_none(val: Optional[int], name: str, minval: Optional[int] = None, maxval: Optional[int] = None) -> None:
    if val is None:
        return
    assert_int_range(val, name, minval, maxval)


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
