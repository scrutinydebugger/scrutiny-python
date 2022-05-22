#    make_sfd.py
#        CLI Command to build and validate a Scrutiny Firmware Description file
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import argparse
from .base_command import BaseCommand
from scrutiny.core.firmware_description import FirmwareDescription
from scrutiny.core.sfd_storage import SFDStorage
from typing import Optional, List


class MakeSFD(BaseCommand):
    _cmd_name_ = 'make-sfd'
    _brief_ = 'Generates a SFD file (Scrutiny Firmware Description) from a given folder containing the required files.'
    _group_ = 'Build Toochain'

    args: List[str]
    parser: argparse.ArgumentParser

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())
        self.parser.add_argument('folder', help='Folder containing the firmware description files.')
        self.parser.add_argument('output', help='Destination file')
        self.parser.add_argument('--install', action="store_true", help='Install the firmwre info file after making it')

    def run(self) -> Optional[int]:
        args = self.parser.parse_args(self.args)
        sfd = FirmwareDescription(args.folder)
        sfd.write(args.output)

        if args.install:
            SFDStorage.install(args.output)

        return 0
