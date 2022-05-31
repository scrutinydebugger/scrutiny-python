#    sfd_storage.py
#        Manipulate the Scrutiny storage for .sfd files
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import appdirs  # type: ignore
import os
from scrutiny.core.firmware_description import FirmwareDescription, MetadataType
import logging
import os
import re

from typing import List

class SFDStorage():

    STORAGE_FOLDER = 'sfd_sotrage'

    @classmethod
    def get_storage_dir(cls) -> str:
        folder = appdirs.user_data_dir(cls.STORAGE_FOLDER, 'scrutiny')
        os.makedirs(folder, exist_ok=True)
        return folder

    @classmethod
    def install(cls, filename: str, ignore_exist=False) -> FirmwareDescription:
        if not os.path.isfile(filename):
            raise ValueError('File "%s" does not exist' % (filename))

        sfd = FirmwareDescription(filename)
        firmware_id_ascii = sfd.get_firmware_id(ascii=True)
        assert isinstance(firmware_id_ascii, str)
        output_file = os.path.join(SFDStorage.get_storage_dir(), firmware_id_ascii)

        if os.path.isfile(output_file) and ignore_exist == False:
            logging.warning('A Scrutiny Firmware Description file with the same firmware ID was already installed. Overwriting.')

        sfd.write(output_file)  # Write the Firmware Description file in storage folder with firmware ID as name
        return sfd

    @classmethod
    def uninstall(cls, firmwareid: str, ignore_not_exist:bool=False) -> None:
        if not cls.is_valid_firmware_id(firmwareid):
            raise ValueError('Invalid firmware ID')

        target_file = os.path.join(SFDStorage.get_storage_dir(), firmwareid)

        if os.path.isfile(target_file):
            os.remove(target_file)
        else:
            if not ignore_not_exist:
                raise ValueError('SFD file with firmware ID %s not found' % (firmwareid))

    @classmethod
    def is_installed(cls, firmwareid: str) -> bool:
        if not cls.is_valid_firmware_id(firmwareid):
            raise ValueError('Invalid firmware ID')

        storage = cls.get_storage_dir()
        filename = os.path.join(storage, firmwareid)
        return os.path.isfile(filename)

    @classmethod
    def get(cls, firmwareid: str) -> FirmwareDescription:
        if not cls.is_valid_firmware_id(firmwareid):
            raise ValueError('Invalid firmware ID')

        storage = cls.get_storage_dir()
        filename = os.path.join(storage, firmwareid)
        if not os.path.isfile(filename):
            raise Exception('Scrutiny Firmware description with firmware ID %s not installed on this system' % (firmwareid))

        return FirmwareDescription(filename)

    @classmethod
    def get_metadata(cls, firmwareid:str) -> MetadataType:
        storage = cls.get_storage_dir()
        filename = os.path.join(storage, firmwareid)
        return FirmwareDescription.read_metadata_from_file(filename)

    @classmethod
    def list(cls) -> List[str]:
        thelist = []
        for filename in os.listdir(cls.get_storage_dir()) :   # file name is firmware ID
            if os.path.isfile(os.path.join(cls.get_storage_dir(), filename)) and cls.is_valid_firmware_id(filename):
                thelist.append(filename)
        return thelist

    @classmethod
    def is_valid_firmware_id(cls, firmware_id:str) -> bool:
        retval = False
        try:
            firmware_id = firmware_id.strip().lower()
            regex = '[0-9a-f]{%d}' % FirmwareDescription.firmware_id_length()*2   # Match only check first line, which is good
            if not re.match(regex, firmware_id):
                raise Exception('regex not match')

            retval = True
        except:
            pass

        return retval



