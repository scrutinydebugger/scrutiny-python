#    __main__.py
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

from scrutiny.cli import CLI
import sys
import os


def main():
    cli = CLI(os.getcwd())
    code = cli.run(sys.argv[1:])
    exit(code)


if __name__ == '__main__':
    main()
