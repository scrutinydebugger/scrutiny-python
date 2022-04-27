#    install_firmware_info.py
#        CLI Command to copy a firmware Information File into the scrutiny storage so it can
#        be automatically loaded by the server upon connection with a device
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import argparse

from .base_command import BaseCommand
from scrutiny.core.sfi_storage import SFIStorage
from typing import Optional, List


class InstallFirmwareInfo(BaseCommand):
    _cmd_name_ = 'install-firmware-info'
    _brief_ = 'Install a Firmware Info file globally for the current user so that it can be loaded automatically upon connection with a device.'
    _group_ = 'Server'

    args: List[str]
    parser: argparse.ArgumentParser

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())
        self.parser.add_argument('file', help='Scrutiny Firmware Information (SFI) file to be installed')

    def run(self) -> Optional[int]:
        args = self.parser.parse_args(self.args)
        SFIStorage.install(args.file)

        return 0
