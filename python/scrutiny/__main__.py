#!/usr/bin/env python3

from scrutiny.cli import CLI
import sys

cli = CLI(sys.argv[1:])
code = cli.run()
exit(code)