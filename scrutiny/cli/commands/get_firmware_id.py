#    get_firmware_id.py
#        CLI Command to generate a unique ID from a .elf file and optionally writes that ID
#        to the file by a search and replace approach so that the device can broadcast its
#        ID once flashed by this firmware.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import argparse
import hashlib
import mmap
import os
import logging
from binascii import hexlify

from .base_command import BaseCommand
from typing import Optional, List


class GetFirmwareId(BaseCommand):
    _cmd_name_ = 'get-firmware-id'
    _brief_ = 'Extract a unique hash from a binary firmware used for device identification.'
    _group_ = 'Build Toochain'

    DEFAULT_NAME = 'firmwareid'
    BUF_SIZE = 0x10000

    args: List[str]
    parser: argparse.ArgumentParser

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())
        self.parser.add_argument('filename', help='The binary fimware to read')
        self.parser.add_argument('--output', default=None, help='The output path of the firmwareid file')
        self.parser.add_argument('--apply', action='store_true',
                                 help='When set, tag the firmware binary file with the new firmware-id hash by replacing the compiled placeholder.')

    def run(self) -> Optional[int]:
        import scrutiny.core.firmware_id as firmware_id

        args = self.parser.parse_args(self.args)
        filename = os.path.normpath(args.filename)

        if args.output is None:
            output_file = None
        elif os.path.isdir(args.output):
            output_file = os.path.join(args.output, self.DEFAULT_NAME)
        else:
            output_file = args.output

        with open(filename, "rb") as f:
            s = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            pos = s.find(firmware_id.PLACEHOLDER);
            if pos == -1:
                raise Exception(
                    "Binary file does not contains Scrutiny placeholder. Either it is already tagged or the file hasn't been compiled with a full scrutiny-lib")

            logging.debug('Found scrutiny placeholder at address 0x%08x' % pos)
            sha256 = hashlib.sha256()
            while True:
                data = f.read(self.BUF_SIZE)
                if not data:
                    break
                sha256.update(data)
            hash256 = bytes.fromhex(sha256.hexdigest())
            thehash_bin = bytes([a ^ b for a, b in zip(hash256[0:16], hash256[16:32])])    # Reduces from 256 to 128 bits
            thehash_str = hexlify(thehash_bin).decode('ascii')

        if output_file is None:
            print(thehash_str, flush=True, end='')
        else:
            with open(output_file, 'w') as f:
                f.write(thehash_str)

        if args.apply:
            with open(filename, "rb+") as f:
                f.seek(pos)
                f.write(thehash_bin)
                logging.debug('Wrote new hash %s at address 0x%08x' % (thehash_str, pos))

        return 0
