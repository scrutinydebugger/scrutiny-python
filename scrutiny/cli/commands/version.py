#    version.py
#        A command line utility that outputs the scrutiny version. Used for release purpose
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['Version']

import argparse

from .base_command import BaseCommand
from scrutiny.tools.typing import *


class Version(BaseCommand):
    _cmd_name_ = 'version'
    _brief_ = 'Display the Scrutiny version string'
    _group_ = 'Development'

    args: List[str]
    parser: argparse.ArgumentParser

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())
        self.parser.add_argument('--format', choices=['full', 'short'], default='full', help='The version format')

    def run(self) -> Optional[int]:
        import scrutiny
        args = self.parser.parse_args(self.args)

        if args.format == 'full':
            print(f"Scrutiny Debugger v{scrutiny.__version__}\n(c) {scrutiny.__author__} (License : {scrutiny.__license__})")
        if args.format == 'short':
            print(f"{scrutiny.__version__}")

        return 0
