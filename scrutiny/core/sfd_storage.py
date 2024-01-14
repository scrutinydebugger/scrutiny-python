#    sfd_storage.py
#        Manipulate the Scrutiny storage for .sfd files
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import appdirs  # type: ignore
import os
from scrutiny.core.firmware_description import FirmwareDescription, MetadataType
import logging
import os
import re
import tempfile
import types

from typing import List, Optional, Type, Literal


class TempStorageWithAutoRestore:
    """This is used to set a temporary SFD storage. Mainly used for unit tests"""
    storage: "SFDStorageManager"

    def __init__(self, storage: "SFDStorageManager") -> None:
        self.storage = storage

    def __enter__(self) -> "TempStorageWithAutoRestore":
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[types.TracebackType]) -> Literal[False]:
        self.restore()
        return False

    def restore(self) -> None:
        self.storage.restore_storage()


class SFDStorageManager:

    temporary_dir: Optional["tempfile.TemporaryDirectory[str]"]
    folder: str

    @classmethod
    def clean_firmware_id(self, firmwareid: str) -> str:
        """Normalize the firmware ID"""
        if not isinstance(firmwareid, str):
            raise ValueError('Firmware ID must be a string')

        return firmwareid.lower().strip()

    def __init__(self, folder: str) -> None:
        self.folder = folder
        self.temporary_dir = None
        os.makedirs(self.folder, exist_ok=True)

    def use_temp_folder(self) -> TempStorageWithAutoRestore:
        """Require the storage manager to switch to a temporary directory. Used for unit testing"""
        self.temporary_dir = tempfile.TemporaryDirectory()
        return TempStorageWithAutoRestore(self)

    def restore_storage(self) -> None:
        """Require the storage manager to work on the real directory and not a temporary directory"""
        self.temporary_dir = None

    def get_storage_dir(self) -> str:
        """Ge the actual storage directory"""
        if self.temporary_dir is not None:
            return self.temporary_dir.name

        return self.folder

    def install(self, filename: str, ignore_exist: bool = False) -> FirmwareDescription:
        """Install a Scrutiny Firmware Description file (SFD) from a filename into the global storage. 
        Once installed, it can be loaded when communication starts with a device that identify
        itself with an ID that matches this SFD"""
        if not os.path.isfile(filename):
            raise ValueError('File "%s" does not exist' % (filename))

        sfd = FirmwareDescription(filename)
        self.install_sfd(sfd, ignore_exist=ignore_exist)
        return sfd

    def install_sfd(self, sfd: FirmwareDescription, ignore_exist: bool = False) -> None:
        """Install a Scrutiny Firmware Description (SFD) object into the global storage. 
        Once isntalled, it can be loaded when communication starts with a device that identify
        itself with an ID that matches this SFD"""
        firmware_id_ascii = self.clean_firmware_id(sfd.get_firmware_id_ascii())
        output_file = os.path.join(self.get_storage_dir(), firmware_id_ascii)

        if os.path.isfile(output_file) and ignore_exist == False:
            logging.warning('A Scrutiny Firmware Description file with the same firmware ID was already installed. Overwriting.')

        sfd.write(output_file)  # Write the Firmware Description file in storage folder with firmware ID as name

    def uninstall(self, firmwareid: str, ignore_not_exist: bool = False) -> None:
        """Remove a Scrutiny Firmware Description (SFD) with given ID from the global storage"""
        firmwareid = self.clean_firmware_id(firmwareid)
        if not self.is_valid_firmware_id(firmwareid):
            raise ValueError('Invalid firmware ID')

        target_file = os.path.join(self.get_storage_dir(), firmwareid)

        if os.path.isfile(target_file):
            os.remove(target_file)
        else:
            if not ignore_not_exist:
                raise ValueError('SFD file with firmware ID %s not found' % (firmwareid))

    def is_installed(self, firmwareid: str) -> bool:
        """Tells if a SFD file with given ID exists in global storage"""
        firmwareid = self.clean_firmware_id(firmwareid)
        if not self.is_valid_firmware_id(firmwareid):
            return False

        storage = self.get_storage_dir()
        filename = os.path.join(storage, firmwareid)
        return os.path.isfile(filename)

    def get(self, firmwareid: str) -> FirmwareDescription:
        """Returns the FirmwareDescription object from the global storage that has the given firmware ID """
        firmwareid = self.clean_firmware_id(firmwareid)
        if not self.is_valid_firmware_id(firmwareid):
            raise ValueError('Invalid firmware ID')

        storage = self.get_storage_dir()
        filename = os.path.join(storage, firmwareid)
        if not os.path.isfile(filename):
            raise Exception('Scrutiny Firmware description with firmware ID %s not installed on this system' % (firmwareid))

        return FirmwareDescription(filename)

    def get_metadata(self, firmwareid: str) -> MetadataType:
        """Reads only the metadata from the Firmware DEscription file in the global storage identified by the given ID"""
        storage = self.get_storage_dir()
        firmwareid = self.clean_firmware_id(firmwareid)
        filename = os.path.join(storage, firmwareid)
        return FirmwareDescription.read_metadata_from_sfd_file(filename)

    def list(self) -> List[str]:
        """Returns a list of firmware ID installed in the global storage"""
        thelist = []
        for filename in os.listdir(self.get_storage_dir()):   # file name is firmware ID
            if os.path.isfile(os.path.join(self.get_storage_dir(), filename)) and self.is_valid_firmware_id(filename):
                thelist.append(filename)
        return thelist

    @classmethod
    def is_valid_firmware_id(cls, firmware_id: str) -> bool:
        """Returns True if the given string respect the expected format for a firmware ID"""
        retval = False
        try:
            firmware_id = cls.clean_firmware_id(firmware_id)
            regex = '[0-9a-f]{%d}' % FirmwareDescription.firmware_id_length() * 2   # Match only check first line, which is good
            if not re.match(regex, firmware_id):
                raise Exception('regex not match')

            retval = True
        except Exception:
            pass

        return retval


GLOBAL_STORAGE = os.path.join(appdirs.user_data_dir('scrutiny'), 'sfd_storage')
SFDStorage = SFDStorageManager(GLOBAL_STORAGE)
