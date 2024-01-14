#    firmware_description.py
#        Contains the class that represent a Scrutiny Firmware Description file.
#        A .sfd is a file that holds all the data related to a firmware and is identified
#        by a unique ID.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import zipfile
import os
import json
import logging

import scrutiny.core.firmware_id as firmware_id
from scrutiny.core.varmap import VarMap
from scrutiny.core.variable import Variable
from scrutiny.server.datastore.datastore import Datastore
from scrutiny.server.datastore.entry_type import EntryType
from scrutiny.core.alias import Alias
from scrutiny.core.basic_types import *

from typing import List, Dict, Any, Tuple, Generator, TypedDict, cast, IO, Optional, Union


class GenerationInfoType(TypedDict, total=False):
    """
    Metadata about the environment of the file creator
    """
    time: int
    python_version: str
    scrutiny_version: str
    system_type: str


class MetadataType(TypedDict, total=False):
    """
    Firmware Description metadata. Used for display in the UI (Communicated through API)
    """
    project_name: str
    author: str
    version: str
    generation_info: GenerationInfoType


class FirmwareDescription:
    """
    Scrutiny Firmware Description (SFD) is an object that contains all the relevant data about a firmware.
    It mainly knows its firmware ID and the list of variables with their location.
    Upon connection with a device, the correct SFD must be loaded, found with the firmware ID
    """
    COMPRESSION_TYPE = zipfile.ZIP_DEFLATED

    varmap: VarMap
    metadata: MetadataType
    firmwareid: bytes
    aliases: Dict[str, Alias]

    varmap_filename: str = 'varmap.json'
    metadata_filename: str = 'metadata.json'
    firmwareid_filename: str = 'firmwareid'
    alias_file: str = 'alias.json'

    logger = logging.getLogger('FirmwareDescription')

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
        """
        Reads a folder just like if it was an unzipped Scrutiny Firmware Description (SFD) file.
        Used to build the SFD
        """
        if not os.path.isdir(folder):
            raise Exception("Folder %s does not exist" % folder)

        for file in self.REQUIRED_FILES:
            if not os.path.isfile(os.path.join(folder, file)):
                raise Exception('Missing %s' % file)

        metadata_file = os.path.join(folder, self.metadata_filename)
        with open(metadata_file, 'rb') as f:
            self.metadata = self.read_metadata(f)

        with open(os.path.join(folder, self.firmwareid_filename), 'rb') as f:
            self.firmwareid = self.read_firmware_id(f)

        self.varmap = self.read_varmap_from_filesystem(folder)

        self.aliases = {}
        if os.path.isfile(os.path.join(folder, self.alias_file)):
            with open(os.path.join(folder, self.alias_file), 'rb') as f:
                aliases = self.read_aliases(f, self.varmap)
                self.append_aliases(aliases)

    @classmethod
    def read_metadata_from_sfd_file(cls, filename: str) -> MetadataType:
        with zipfile.ZipFile(filename, mode='r', compression=cls.COMPRESSION_TYPE) as sfd:
            with sfd.open(cls.metadata_filename) as f:
                metadata = cls.read_metadata(f)

        return metadata

    def load_from_file(self, filename: str) -> None:
        """Reads a Scrutiny Frimware Description file (.sfd) which is just a .zip containing bunch of json files """
        with zipfile.ZipFile(filename, mode='r', compression=self.COMPRESSION_TYPE) as sfd:
            with sfd.open(self.firmwareid_filename) as f:
                self.firmwareid = self.read_firmware_id(f)  # This is not a Json file. Content is raw.

            with sfd.open(self.metadata_filename, 'r') as f:
                self.metadata = self.read_metadata(f)   # This is a json file

            with sfd.open(self.varmap_filename, 'r') as f:
                self.varmap = VarMap(f.read())  # Json file

            self.aliases = {}
            if self.alias_file in sfd.namelist():
                with sfd.open(self.alias_file, 'r') as f:
                    self.append_aliases(self.read_aliases(f, self.varmap))

    @classmethod
    def read_firmware_id(cls, f: IO[bytes]) -> bytes:
        return bytes.fromhex(f.read().decode('ascii'))

    @classmethod
    def read_metadata(cls, f: IO[bytes]) -> MetadataType:
        return cast(MetadataType, json.loads(f.read().decode('utf8')))

    @classmethod
    def read_aliases(cls, f: IO[bytes], varmap: VarMap) -> Dict[str, Alias]:
        aliases_raw: Dict[str, Any] = json.loads(f.read().decode('utf8'))
        aliases: Dict[str, Alias] = {}
        for k in aliases_raw:
            alias = Alias.from_dict(k, aliases_raw[k])
            try:
                alias.set_target_type(cls.get_alias_target_type(alias, varmap))
            except Exception as e:
                cls.logger.error("Cannot read alias. %s" % str(e))

            aliases[k] = alias

        return aliases

    @classmethod
    def get_alias_target_type(cls, alias: Alias, varmap: VarMap) -> EntryType:
        """ Finds the referred entry and gives this datatype. Alias do not have a datatype by themselves """
        if varmap.has_var(alias.get_target()):
            return EntryType.Var
        elif Datastore.is_rpv_path(alias.get_target()):
            return EntryType.RuntimePublishedValue
        else:
            raise Exception('Alias %s is referencing %s which is not a valid Variable or Runtime Published Value' %
                            (alias.get_fullpath(), alias.get_target()))

    @classmethod
    def read_varmap_from_filesystem(cls, path: str) -> VarMap:
        if os.path.isfile(path):
            fullpath = path
        elif os.path.isdir(path):
            fullpath = os.path.join(path, cls.varmap_filename)
        else:
            raise Exception('Cannot find varmap file at %s' % path)

        return VarMap(fullpath)

    def append_aliases(self, aliases: Dict[str, Alias]) -> None:
        """Add some aliases to the actual SFD"""
        for unique_path in aliases:
            if unique_path not in self.aliases:
                self.aliases[unique_path] = aliases[unique_path]
            else:
                logging.warning('Duplicate alias %s. Dropping' % unique_path)

    def write(self, filename: str) -> None:
        """SFD file format is just a .zip with a bunch of JSON (and a firmwareid file)"""
        with zipfile.ZipFile(filename, mode='w', compression=self.COMPRESSION_TYPE) as outzip:
            outzip.writestr(self.firmwareid_filename, self.firmwareid.hex())
            outzip.writestr(self.metadata_filename, json.dumps(self.metadata, indent=4))
            outzip.writestr(self.varmap_filename, self.varmap.get_json())
            outzip.writestr(self.alias_file, self.serialize_aliases(list(self.aliases.values())))

    @classmethod
    def serialize_aliases(cls, aliases: Union[Dict[str, Alias], List[Alias]]) -> bytes:
        """ 
        Takes bunch of alias and return a JSON containing a dict structure like this
        [alias1.fullpath] => alias1,  [alias2.fullpath] => alias2 
        """
        if isinstance(aliases, list):
            zipped = zip(
                [alias.get_fullpath() for alias in aliases],
                [alias.to_dict() for alias in aliases]
            )
        elif isinstance(aliases, dict):
            zipped = zip(
                [aliases[k].get_fullpath() for k in aliases],
                [aliases[k].to_dict() for k in aliases]
            )
        else:
            ValueError('Require a list or a dict of aliases')
        return json.dumps(dict(zipped), indent=4).encode('utf8')

    def get_firmware_id(self) -> bytes:
        return self.firmwareid

    def get_firmware_id_ascii(self) -> str:
        return self.firmwareid.hex().lower()

    def get_endianness(self) -> Endianness:
        return self.varmap.get_endianness()

    def validate(self) -> None:
        if not hasattr(self, 'metadata') or not hasattr(self, 'varmap') or not hasattr(self, 'firmwareid'):
            raise Exception('Firmware Description not loaded correctly')

        self.validate_metadata()
        self.validate_firmware_id()
        self.varmap.validate()

    def validate_firmware_id(self) -> None:
        """Expects a Firmware ID to have the same length as the default placeholder"""
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
        """Returns all variables in this SFD with a Generator to avoid consuming memory."""
        for fullname, vardef in self.varmap.iterate_vars():
            yield (fullname, vardef)

    def get_aliases_for_datastore(self, entry_type: Optional[EntryType] = None) -> Generator[Tuple[str, Alias], None, None]:
        """Returns all alias in this SFD with a Generator to avoid consuming memory."""
        for k in self.aliases:
            if entry_type is None or self.aliases[k].get_target_type() == entry_type:
                yield (self.aliases[k].get_fullpath(), self.aliases[k])

    def get_aliases(self) -> Dict[str, Alias]:
        return self.aliases

    def get_metadata(self) -> MetadataType:
        return self.metadata

    @classmethod
    def firmware_id_length(cls) -> int:
        return len(firmware_id.PLACEHOLDER)
