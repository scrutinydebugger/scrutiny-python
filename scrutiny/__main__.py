#!/usr/bin/env python3

#    __main__.py
#        Entry point of the python module. Launch the CLI.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny.cli import CLI
import sys
import os


def main()-> None:
    cli = CLI(os.getcwd())
    code = cli.run(sys.argv[1:])
    exit(code)


if __name__ == '__main__':
    main()
