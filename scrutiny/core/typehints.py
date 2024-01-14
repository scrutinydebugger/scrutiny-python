#    typehints.py
#        Contains some definition for type hints that are used across all project
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from typing import TypedDict, Callable, Any, List


class GenericCallback:
    """
    This class is a way to workaround the limitation of mypy with assigning callbacks
    to Callable Types
    """
    callback: Callable   # type: ignore

    def __init__(self, callback: Callable) -> None:  # type: ignore
        self.callback = callback

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        assert self.callback is not None
        self.callback(*args, **kwargs)


class EmptyDict(TypedDict):
    pass
