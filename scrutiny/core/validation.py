from typing import Union, Any, Type, List, Tuple, Sequence, Optional


def assert_type(var: Any, types: Union[Type[Any], List[Type], Tuple[Type, ...]], name: str) -> None:
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


def assert_val_in(var: Any, vals: Sequence[Any], name: str) -> None:
    if var not in vals:
        raise ValueError(f"\"{name}\" has an invalid value. Expected one of {vals}")


def assert_int_range(val: int, name: str, minval: Optional[int] = None, maxval: Optional[int] = None) -> None:
    assert_type(val, int, name)
    if minval is not None:
        if val < minval:
            raise ValueError(f"{name} must be greater than {minval}. Got {val}")

    if maxval is not None:
        if val > maxval:
            raise ValueError(f"{name} must be less than {maxval}. Got {val}")


def assert_int_range_if_not_none(val: int, name: str, minval: Optional[int] = None, maxval: Optional[int] = None) -> None:
    if val is None:
        return
    assert_int_range(val, name, minval, maxval)
