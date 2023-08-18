from typing import Union, Any, Type, List, Tuple


def assert_type(var: Any, types: Union[Type[Any], List[Type], Tuple[Type, ...]], name: str):
    if isinstance(types, (list, tuple)):
        typenames: List[str] = [x.__name__ for x in types]
        if not isinstance(var, tuple(types)):
            raise TypeError(f"\"{name}\" type is not one of \"{typenames}\". Got \"{var.__class__.__name__}\" instead")
    else:
        if not isinstance(var, types):
            raise TypeError(f"\"{name}\" is not of type \"{types.__name__}\". Got \"{var.__class__.__name__}\" instead")
