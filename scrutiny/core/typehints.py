#    typehints.py
#        Contains some definition for type hints that are used across all project
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2023 Scrutiny Debugger

from typing import TypedDict


class GenericCallback:
    """
    This class is a way to workaround the limitation of mypy with assigning callbacks
    to Callable Types
    """

    def __init__(self, callback):
        self.callback = callback

    def __call__(self, *args, **kwargs):
        assert self.callback is not None
        self.callback(*args, **kwargs)


class EmptyList:
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not isinstance(v, list):
            raise TypeError('list required')
        if len(v) > 0:
            raise ValueError('list must be empty')
        return []


class EmptyDict(TypedDict):
    pass
