#    install_sfd.py
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import argparse
from .base_command import BaseCommand
from typing import Optional, List


class InstallSFD(BaseCommand):
    _cmd_name_ = 'install-sfd'
    _brief_ = 'Install a SFD file (Scrutiny Firmware Description) globally for the current user so that it can be loaded automatically upon connection with a device.'
    _group_ = 'Server'

    args: List[str]
    parser: argparse.ArgumentParser

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())
        self.parser.add_argument('file', help='Scrutiny Firmware Description (SFD) file to be installed')

    def run(self) -> Optional[int]:
        from scrutiny.core.sfd_storage import SFDStorage

        args = self.parser.parse_args(self.args)
        SFDStorage.install(args.file)

        return 0
