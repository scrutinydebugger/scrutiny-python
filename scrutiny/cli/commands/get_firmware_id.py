#    get_firmware_id.py
#        CLI Command to generate a unique ID from a .elf file and optionally writes that ID
#        to the file by a search and replace approach so that the device can broadcast its
#        ID once flashed by this firmware.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import argparse

import os
import logging

from .base_command import BaseCommand
from typing import Optional, List


class GetFirmwareId(BaseCommand):
    _cmd_name_ = 'get-firmware-id'
    _brief_ = 'Extract a unique hash from a binary firmware used for device identification.'
    _group_ = 'Build Toolchain'

    DEFAULT_NAME = 'firmwareid'

    args: List[str]
    parser: argparse.ArgumentParser

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())
        self.parser.add_argument('filename', help='The binary fimware to read')
        self.parser.add_argument('--output', default=None, help='The output path of the firmwareid file')

    def run(self) -> Optional[int]:
        from scrutiny.core.firmware_parser import FirmwareParser

        args = self.parser.parse_args(self.args)
        filename = os.path.normpath(args.filename)

        if args.output is None:
            output_file = None
        elif os.path.isdir(args.output):
            output_file = os.path.join(args.output, self.DEFAULT_NAME)
        else:
            output_file = args.output

        parser = FirmwareParser(filename)
        if not parser.has_placeholder():
            parser.throw_no_tag_error()

        if output_file is None:
            print(parser.get_firmware_id_ascii(), flush=True, end='')
        else:
            with open(output_file, 'w') as f:
                f.write(parser.get_firmware_id_ascii())

        return 0
