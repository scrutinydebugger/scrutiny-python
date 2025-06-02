#    user_command.py
#        Scrutiny protocol command to launch user defined functions in the device.
#        It's a way of leveraging the existing communication protocol for other purpose than
#        Scrutiny debugging.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

__all__ = ['UserCommand']

from .base_command import BaseCommand


class UserCommand(BaseCommand):
    _cmd_id = 4
