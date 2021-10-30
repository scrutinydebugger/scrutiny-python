#!/usr/bin/env python3

from scrutiny.cli import CLI
import sys
import os

cli = CLI(os.getcwd())
code = cli.run(sys.argv[1:])
exit(code)