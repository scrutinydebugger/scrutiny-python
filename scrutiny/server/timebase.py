#    timebase.py
#        The timebase used by the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['server_timebase']

from scrutiny.tools.timebase import RelativeTimebase

server_timebase = RelativeTimebase()
