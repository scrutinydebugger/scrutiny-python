#    uninstall_firmware_info.py
#        CLI Command to remove a Firmware Information File from the scrutiny storage
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import argparse

from .base_command import BaseCommand
from scrutiny.core.sfi_storage import SFIStorage
from typing import Optional, List


class UninstallFirmwareInfo(BaseCommand):
    _cmd_name_ = 'uninstall-firmware-info'
    _brief_ = 'Uninstall a Firmware Info file globally for the current user.'
    _group_ = 'Server'

    args: List[str]
    parser: argparse.ArgumentParser

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())
        self.parser.add_argument('firmwareid', help='Firmware ID of the Scrutiny Firmware Info')
        self.parser.add_argument('--quiet', action="store_true", help='Do not report error if not installed')

    def run(self) -> Optional[int]:
        args = self.parser.parse_args(self.args)
        error = None
        try:
            SFIStorage.uninstall(args.firmwareid)
        except Exception as e:
            error = e

        if error is not None:
            if not args.quiet:
                raise error

        return 0
