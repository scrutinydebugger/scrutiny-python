#    tag_firmware_id.py
#        Command to write the firmware ID into a freshly compiled binary
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import argparse

import os

from .base_command import BaseCommand
from typing import Optional, List


class TagFirmwareID(BaseCommand):
    _cmd_name_ = 'tag-firmware-id'
    _brief_ = 'Writes the firmware id into a freshly compiled binary'
    _group_ = 'Build Toolchain'

    args: List[str]
    parser: argparse.ArgumentParser

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())
        self.parser.add_argument('src', help='The input untagged binary')
        self.parser.add_argument('dst', nargs='?', default=None, help='The output tagged binary')
        self.parser.add_argument('--inplace', action='store_true', default=False,
                                 help='Write the firmware ID into the source file. No output file is needed when tagged inplace')

    def run(self) -> Optional[int]:
        from scrutiny.core.firmware_parser import FirmwareParser

        args = self.parser.parse_args(self.args)
        src = os.path.normpath(args.src)
        if args.inplace:
            if args.dst is not None:
                raise Exception('No output file must be provided when using --inplace')
        else:
            if args.dst is None:
                raise Exception('Output file is required')

        parser = FirmwareParser(src)
        if not parser.has_placeholder():
            parser.throw_no_tag_error()

        parser.write_tagged(args.dst)   # inplace if None

        return 0
