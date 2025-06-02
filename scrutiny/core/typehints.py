#    typehints.py
#        Contains some definition for type hints that are used across all project
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

__all__ = ['EmptyDict']

from typing import TypedDict


class EmptyDict(TypedDict):
    pass
