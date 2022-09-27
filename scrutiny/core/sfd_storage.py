#    sfd_storage.py
#        Manipulate the Scrutiny storage for .sfd files
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import appdirs  # type: ignore
import os
from scrutiny.core.firmware_description import FirmwareDescription, MetadataType
import logging
import os
import re
import tempfile

from typing import List


class TempStorageWithAutoRestore:
    def __init__(self, storage):
        self.storage = storage

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.storage.restore_storage()


class SFDStorageManager():

    @classmethod
    def clean_firmware_id(self, firmwareid:str) -> str:
        if not isinstance(firmwareid, str):
            raise ValueError('Firmware ID must be a string')
        
        return firmwareid.lower().strip()

    def __init__(self, folder):
        self.folder = folder
        self.temporary_dir = None
        os.makedirs(self.folder, exist_ok=True)

    def use_temp_folder(self):
        self.temporary_dir = tempfile.TemporaryDirectory()
        return TempStorageWithAutoRestore(self)

    def restore_storage(self):
        self.temporary_dir = None

    def get_storage_dir(self) -> str:
        if self.temporary_dir is not None:
            return self.temporary_dir.name

        return self.folder

    def install(self, filename: str, ignore_exist:bool=False) -> FirmwareDescription:
        if not os.path.isfile(filename):
            raise ValueError('File "%s" does not exist' % (filename))

        sfd = FirmwareDescription(filename)
        self.install_sfd(sfd, ignore_exist=ignore_exist)
        return sfd
        
    
    def install_sfd(self, sfd:FirmwareDescription, ignore_exist:bool=False) -> None:
        firmware_id_ascii = self.clean_firmware_id(sfd.get_firmware_id_ascii())
        output_file = os.path.join(self.get_storage_dir(), firmware_id_ascii)

        if os.path.isfile(output_file) and ignore_exist == False:
            logging.warning('A Scrutiny Firmware Description file with the same firmware ID was already installed. Overwriting.')

        sfd.write(output_file)  # Write the Firmware Description file in storage folder with firmware ID as name

    def uninstall(self, firmwareid: str, ignore_not_exist: bool = False) -> None:
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
        firmwareid = self.clean_firmware_id(firmwareid)
        if not self.is_valid_firmware_id(firmwareid):
            raise ValueError('Invalid firmware ID')

        storage = self.get_storage_dir()
        filename = os.path.join(storage, firmwareid)
        return os.path.isfile(filename)

    def get(self, firmwareid: str) -> FirmwareDescription:
        self.clean_firmware_id(firmwareid)
        if not self.is_valid_firmware_id(firmwareid):
            raise ValueError('Invalid firmware ID')

        storage = self.get_storage_dir()
        filename = os.path.join(storage, firmwareid)
        if not os.path.isfile(filename):
            raise Exception('Scrutiny Firmware description with firmware ID %s not installed on this system' % (firmwareid))

        return FirmwareDescription(filename)

    def get_metadata(self, firmwareid: str) -> MetadataType:
        storage = self.get_storage_dir()
        firmwareid = self.clean_firmware_id(firmwareid)
        filename = os.path.join(storage, firmwareid)
        return FirmwareDescription.read_metadata_from_sfd_file(filename)

    def list(self) -> List[str]:
        thelist = []
        for filename in os.listdir(self.get_storage_dir()):   # file name is firmware ID
            if os.path.isfile(os.path.join(self.get_storage_dir(), filename)) and self.is_valid_firmware_id(filename):
                thelist.append(filename)
        return thelist

    @classmethod
    def is_valid_firmware_id(cls, firmware_id: str) -> bool:
        retval = False
        try:
            firmware_id = cls.clean_firmware_id(firmware_id)
            regex = '[0-9a-f]{%d}' % FirmwareDescription.firmware_id_length() * 2   # Match only check first line, which is good
            if not re.match(regex, firmware_id):
                raise Exception('regex not match')

            retval = True
        except:
            pass

        return retval


GLOBAL_STORAGE = appdirs.user_data_dir('sfd_storage', 'scrutiny')
SFDStorage = SFDStorageManager(GLOBAL_STORAGE)
