#    typehints.py
#        Contains some definition for type hints that are used across all project
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

from typing import Literal, Callable


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
