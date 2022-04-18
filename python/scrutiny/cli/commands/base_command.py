#    base_command.py
#        Abstract class for all commands. Used to automatically find all available commands
#        through reflection
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import argparse
from abc import ABC


class BaseCommand(ABC):

    @classmethod
    def get_name(cls):
        return cls._cmd_name_

    @classmethod
    def get_brief(cls):
        return cls._brief_

    @classmethod
    def get_group(cls):
        if hasattr(cls, '_group_'):
            return cls._group_
        else:
            return ''

    @classmethod
    def get_prog(cls):
        return 'scrutiny ' + cls.get_name()
