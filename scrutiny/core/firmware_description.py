#    firmware_description.py
#        Contains the class that represent a Scrutiny Firmware Description file.
#        A .sfd is a file that holds all the data related to a firmware and is identified
#        by a unique ID.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import zipfile
import os
import json
import logging

import scrutiny.core.firmware_id as firmware_id
from scrutiny.core.varmap import VarMap
from scrutiny.core import Variable

from typing import List, Union, Dict, Any, Tuple, Generator, TypedDict


class GenerationInfoType(TypedDict, total=False):
    time: int
    python_version: str
    scrutiny_version: str
    system_type: str


class MetadataType(TypedDict, total=False):
    project_name: str
    author: str
    version: str
    generation_info: GenerationInfoType


class FirmwareDescription:
    COMPRESSION_TYPE = zipfile.ZIP_DEFLATED

    varmap: VarMap
    metadata: MetadataType
    firmwareid: bytes

    varmap_filename: str = 'varmap.json'
    metadata_filename: str = 'metadata.json'
    firmwareid_filename: str = 'firmwareid'

    REQUIRED_FILES: List[str] = [
        firmwareid_filename,
        metadata_filename,
        varmap_filename
    ]

    def __init__(self, file_folder: str):
        if os.path.isdir(file_folder):
            self.load_from_folder(file_folder)
        elif os.path.isfile(file_folder):
            self.load_from_file(file_folder)

        self.validate()

    def load_from_folder(self, folder: str) -> None:
        if not os.path.isdir(folder):
            raise Exception("Folder %s does not exist" % folder)

        for file in self.REQUIRED_FILES:
            if not os.path.isfile(os.path.join(folder, file)):
                raise Exception('Missing %s' % file)

        metadata_file = os.path.join(folder, self.metadata_filename)
        with open(metadata_file) as f:
            self.metadata = json.loads(f.read())

        with open(os.path.join(folder, self.firmwareid_filename)) as f:
            self.firmwareid = bytes.fromhex(f.read())

        self.varmap = VarMap(os.path.join(folder, self.varmap_filename))

    @classmethod
    def read_metadata_from_file(cls, filename: str) -> MetadataType:
        with zipfile.ZipFile(filename, mode='r', compression=cls.COMPRESSION_TYPE) as sfd:
            with sfd.open(cls.metadata_filename) as f:
                metadata = json.loads(f.read())

        return metadata

    def load_from_file(self, filename: str) -> None:
        with zipfile.ZipFile(filename, mode='r', compression=self.COMPRESSION_TYPE) as sfd:
            with sfd.open(self.firmwareid_filename) as f:
                self.firmwareid = bytes.fromhex(f.read().decode('ascii'))

            with sfd.open(self.metadata_filename) as f:
                self.metadata = json.loads(f.read())

            with sfd.open(self.varmap_filename) as f:
                self.varmap = VarMap(f.read())

    def write(self, filename: str) -> None:
        with zipfile.ZipFile(filename, mode='w', compression=self.COMPRESSION_TYPE) as outzip:
            outzip.writestr(self.firmwareid_filename, self.firmwareid.hex())
            outzip.writestr(self.metadata_filename, json.dumps(self.metadata, indent=4))
            outzip.writestr(self.varmap_filename, self.varmap.get_json())

    def get_firmware_id(self, ascii: bool = True) -> Union[bytes, str]:
        if ascii:
            return self.firmwareid.hex()
        else:
            return self.firmwareid

    def validate(self) -> None:
        if not hasattr(self, 'metadata') or not hasattr(self, 'varmap') or not hasattr(self, 'firmwareid'):
            raise Exception('Firmware Descritpion not loaded correctly')

        self.validate_metadata()
        self.validate_firmware_id()
        self.varmap.validate()

    def validate_firmware_id(self) -> None:
        if len(self.firmwareid) != self.firmware_id_length():
            raise Exception('Firmware ID seems to be the wrong length. Found %d bytes, expected %d bytes' %
                            (len(self.firmwareid), len(firmware_id.PLACEHOLDER)))

    def validate_metadata(self) -> None:
        if 'project_name' not in self.metadata or not self.metadata['project_name']:
            logging.warning('No project name defined in %s' % self.metadata_filename)

        if 'version' not in self.metadata or not self.metadata['version']:
            logging.warning('No version defined in %s' % self.metadata_filename)

        if 'author' not in self.metadata or not self.metadata['author']:
            logging.warning('No author defined in %s' % self.metadata_filename)

    def get_vars_for_datastore(self) -> Generator[Tuple[str, Variable], None, None]:
        for fullname, vardef in self.varmap.iterate_vars():
            yield (fullname, vardef)

    def get_metadata(self):
        return self.metadata

    @classmethod
    def firmware_id_length(cls) -> int:
        return len(firmware_id.PLACEHOLDER)
