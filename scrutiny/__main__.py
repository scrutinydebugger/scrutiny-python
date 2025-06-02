#!/usr/bin/env python3

#    __main__.py
#        Entry point of the python module. Launch the CLI.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

from scrutiny.cli import CLI
import sys
import os


def scrutiny_server() -> None:
    cli = CLI(os.getcwd())
    code = cli.run(['server'] + sys.argv[1:])
    sys.exit(code)


def scrutiny_gui_with_server() -> None:
    cli = CLI(os.getcwd())
    code = cli.run(['gui', '--start-local-server', '--auto-connect'] + sys.argv[1:])
    sys.exit(code)


def scrutiny_cli() -> None:
    cli = CLI(os.getcwd())
    code = cli.run(sys.argv[1:])
    sys.exit(code)


if __name__ == '__main__':
    scrutiny_cli()
