#!/usr/bin/env python3

#    __main__.py
#        Entry point of the python module. Launch the CLI.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

# nuitka-project-if: {OS} == "Windows":
#     nuitka-project: --windows-console-mode=hide
# nuitka-project-else:
#     nuitka-project: --windows-console-mode=disabled

from scrutiny.entry_points.scrutiny import scrutiny_cli

if __name__ == '__main__':
    scrutiny_cli()
