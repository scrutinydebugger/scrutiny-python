#    firmware_parser.py
#        Reads a compiled firmware and provide tools to read or write the firmware ID
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import hashlib
import mmap
import logging
import scrutiny.core.firmware_id as firmware_id
import os
from binascii import hexlify
import shutil

from typing import Optional


class FirmwareParser:
    """
    This class can read a freshly compiled firmware then generate a firmware ID and also write this
    firmware ID into the binary
    """
    BUF_SIZE = 0x10000
    NO_TAG_ERROR = "Binary file does not contains Scrutiny placeholder. Either it is already tagged or the file hasn't been compiled with a full scrutiny-lib"

    filename: str
    content: bytes
    logger: logging.Logger
    placeholder_location: Optional[int]
    firmware_id: Optional[bytes]

    def __init__(self, filename: str):
        self.filename = os.path.normpath(filename)

        if not os.path.isfile(self.filename):
            raise Exception('File %s does not exist' % filename)

        self.logger = logging.getLogger(self.__class__.__name__)
        self.firmware_id = None
        self.placeholder_location = None

        with open(filename, "rb") as f:
            s = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            pos = s.find(firmware_id.PLACEHOLDER)
            if pos != -1:
                self.logger.debug('Found scrutiny placeholder at address 0x%08x' % pos)
                self.placeholder_location = pos

                sha256 = hashlib.sha256()
                while True:
                    data = f.read(self.BUF_SIZE)
                    if not data:
                        break
                    sha256.update(data)
                hash256 = bytes.fromhex(sha256.hexdigest())
                self.firmware_id = bytes([a ^ b for a, b in zip(hash256[0:16], hash256[16:32])])    # Reduces from 256 to 128 bits

    def has_placeholder(self) -> bool:
        """True if the parsed binary contains a placeholder ID ready to be replaced"""
        return self.placeholder_location is not None

    def throw_no_tag_error(self) -> None:
        raise Exception(self.NO_TAG_ERROR)

    def get_firmware_id(self) -> bytes:
        """Return the firmware ID generated while parsing an untagged binary"""
        if self.firmware_id is None:
            self.throw_no_tag_error()

        assert self.firmware_id is not None  # for mypy
        return self.firmware_id

    def get_firmware_id_ascii(self) -> str:
        return hexlify(self.get_firmware_id()).decode('ascii')

    def write_tagged(self, dst: Optional[str]) -> None:
        """
        Write back the firmware ID into an untagged one. If dst is set, make a copy, if None, write directly to it.
        """
        if self.firmware_id is None or not self.has_placeholder():
            self.throw_no_tag_error()

        # mypy assertions
        assert self.placeholder_location is not None
        assert self.firmware_id is not None

        src = os.path.normcase(os.path.normpath(os.path.abspath(os.path.realpath(self.filename))))
        if dst is None:
            dst = src
        dst = os.path.normcase(os.path.normpath(os.path.abspath(os.path.realpath(dst))))
        if src != dst:
            shutil.copyfile(src, dst)

        with open(dst, "rb+") as f:
            f.seek(self.placeholder_location)
            f.write(self.get_firmware_id())
            self.logger.debug('Wrote new hash %s at address 0x%08x' % (self.get_firmware_id_ascii(), self.placeholder_location))
