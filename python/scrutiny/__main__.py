#!/usr/bin/env python3

#    __main__.py
#        Entry point of the python module. Launch the CLI.
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

from scrutiny.cli import CLI
import sys
import os

cli = CLI(os.getcwd())
code = cli.run(sys.argv[1:])
exit(code)
