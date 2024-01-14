#    make_sfd.py
#        CLI Command to build and validate a Scrutiny Firmware Description file
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import argparse
from .base_command import BaseCommand
from typing import Optional, List


class MakeSFD(BaseCommand):
    _cmd_name_ = 'make-sfd'
    _brief_ = 'Generates a SFD file (Scrutiny Firmware Description) from a given folder containing the required files.'
    _group_ = 'Build Toolchain'

    args: List[str]
    parser: argparse.ArgumentParser

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())
        self.parser.add_argument('folder', help='Folder containing the firmware description files.')
        self.parser.add_argument('output', help='Destination file')
        self.parser.add_argument('--install', action="store_true", help='Install the firmware info file after making it')

    def run(self) -> Optional[int]:
        from scrutiny.core.firmware_description import FirmwareDescription
        from scrutiny.core.sfd_storage import SFDStorage
        args = self.parser.parse_args(self.args)
        sfd = FirmwareDescription(args.folder)
        sfd.write(args.output)

        if args.install:
            SFDStorage.install(args.output)

        return 0
