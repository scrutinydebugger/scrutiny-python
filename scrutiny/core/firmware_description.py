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
import math

import scrutiny.core.firmware_id as firmware_id
from scrutiny.core.varmap import VarMap
from scrutiny.core.variable import Variable
from scrutiny.server.datastore import EntryType, Datastore

from typing import List,  Dict, Any, Tuple, Generator, TypedDict, cast, IO, Optional, Union


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

class AliasDefinition:
    fullpath:str
    target:str
    target_type:Optional[EntryType]
    gain:Optional[float]
    offset:Optional[float]
    min:Optional[float]
    max:Optional[float]

    @classmethod 
    def from_json(cls, fullpath:str, json_str:str) -> 'AliasDefinition':
        d = json.loads(json_str)
        return cls.from_dict(fullpath, d)

    @classmethod
    def from_dict(cls, fullpath:str, obj:Dict[str, Any]) -> 'AliasDefinition':
        assert 'target' in obj, 'Missing target'
        
        obj_out = cls(
            fullpath = fullpath,
            target = obj['target'],
            target_type = obj['target_type'] if 'target_type' in obj else None,
            gain = obj['gain'] if 'gain' in obj else None,
            offset = obj['offset'] if 'offset' in obj else None,
            min = obj['min'] if 'min' in obj else None,
            max = obj['max'] if 'max' in obj else None
        )
        obj_out.validate()
        return obj_out
    
    def __init__(self, fullpath:str, target:str, target_type:Optional[EntryType]=None, gain:Optional[float]=None, offset:Optional[float]=None, min:Optional[float]=None, max:Optional[float]=None):
        
        
        
        self.fullpath = fullpath
        if target_type is not None:
            target_type = EntryType(target_type)
            if target_type == EntryType.Alias:
                raise ValueError("Cannot make an alias over another alias.")
            self.target_type = EntryType(target_type)
        else:
            self.target_type = None
        self.target = target
        self.gain = float(gain) if gain is not None else None
        self.offset = float(offset) if offset is not None else None
        self.min = float(min) if min is not None else None
        self.max = float(max) if max is not None else None


    def validate(self):
        if not self.fullpath or not isinstance(self.fullpath, str):
            raise ValueError('fullpath is not valid')
        
        if self.target_type is not None:
            EntryType(self.target_type) # Make sure ocnversion is possible
        
        if not self.target or not isinstance(self.target, str):
            raise ValueError('Alias (%s) target is not valid' % self.fullpath)

        if  not isinstance(self.get_gain(), float) or math.isnan(self.get_gain()):
            raise ValueError('Alias (%s) gain is not a valid float' % self.fullpath)
        if  not isinstance(self.get_offset(), float) or math.isnan(self.get_offset()):
            raise ValueError('Alias (%s) offset is not a valid float' % self.fullpath)
        if  not isinstance(self.get_min(), float) or math.isnan(self.get_min()):
            raise ValueError('Alias (%s) minimum value is not a valid float' % self.fullpath)
        if  not isinstance(self.get_max(), float) or math.isnan(self.get_max()):
            raise ValueError('Alias (%s) maximum is not a valid float' % self.fullpath)

        if self.get_min() > self.get_max():
            raise ValueError('Max (%s) > min (%s)' % (str(self.max), str(self.min)))
            
        if not math.isfinite(self.get_gain()):
             raise ValueError('Gain is not a finite value')
            
        if not math.isfinite(self.get_offset()):
             raise ValueError('Gain is not a finite value')

    
    def to_dict(self) -> Dict[str, Any]:
        d:Dict[str, Any] = dict(target=self.target, target_type=self.target_type)

        if self.gain is not None and self.gain != 1.0:
            d['gain'] = self.gain

        if self.offset is not None and self.offset != 0.0:
            d['offset'] = self.offset

        if self.min is not None and self.min != float('-inf'):
            d['min'] = self.min

        if self.max is not None and self.max != float('inf'):
            d['max'] = self.max
        
        return d
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    def get_fullpath(self) -> str:
        return self.fullpath

    def get_target(self) -> str:
        return self.target
    
    def get_target_type(self) -> EntryType:
        if self.target_type is None:
            raise RuntimeError('Target type for alias %s is not set' % self.get_fullpath())
        return self.target_type
    
    def set_target_type(self, target_type:EntryType):
        if self.target_type == EntryType.Alias:
            raise ValueError('Alias %s point onto another alias (%s)' % (self.get_fullpath(), self.get_target()))
        self.target_type = target_type

    def get_min(self) -> float:
        return self.min if self.min is not None else float('-inf')
    
    def get_max(self) -> float:
        return self.max if self.max is not None else float('inf')

    def get_gain(self) -> float:
        return self.gain if self.gain is not None else 1.0
    
    def get_offset(self) -> float:
        return self.offset if self.offset is not None else 0.0

class FirmwareDescription:
    COMPRESSION_TYPE = zipfile.ZIP_DEFLATED

    varmap: VarMap
    metadata: MetadataType
    firmwareid: bytes
    aliases:Dict[str, AliasDefinition]

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
        """
        Reads a Scrutiny Frimware Description file (.sfd) which is just a .zip containing bunch of json files 
        """
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
    def read_firmware_id(cls, f:IO[bytes] ) -> bytes:
        return bytes.fromhex(f.read().decode('ascii'))
    
    @classmethod
    def read_metadata(cls, f:IO[bytes]) -> MetadataType:
        return cast(MetadataType, json.loads(f.read().decode('utf8')))
    
    @classmethod
    def read_aliases(cls, f:IO[bytes], varmap:VarMap) -> Dict[str, AliasDefinition]:
        aliases_raw:Dict[str, Any] = json.loads(f.read().decode('utf8'))
        aliases:Dict[str, AliasDefinition] = {}
        for k in aliases_raw:
            alias = AliasDefinition.from_dict(k, aliases_raw[k])
            try:
                alias.set_target_type(cls.get_alias_target_type(alias, varmap))
            except Exception as e: 
                cls.logger.error("Cannot read alias. %s" % str(e))

            aliases[k] = alias
            
        return aliases
    
    @classmethod
    def get_alias_target_type(cls, alias:AliasDefinition, varmap:VarMap) -> EntryType:
        if varmap.has_var(alias.get_target()):
            return EntryType.Var
        elif Datastore.is_rpv_path(alias.get_target()):
            return EntryType.RuntimePublishedValue
        else:
            raise Exception('Alias %s does not seems to point towards a valid Variable or Runtime Published Value' % alias.get_fullpath())
    
    @classmethod
    def read_varmap_from_filesystem(cls, path:str) -> VarMap: 
        if os.path.isfile(path):
            fullpath = path
        elif os.path.isdir(path):
            fullpath = os.path.join(path, cls.varmap_filename)
        else:
            raise Exception('Cannot find varmap file at %s' % path)
        
        return VarMap(fullpath)


    def append_aliases(self, aliases : Dict[str, AliasDefinition]) -> None:
        for unique_path in aliases:
            if unique_path not in self.aliases:
                self.aliases[unique_path] = aliases[unique_path]
            else:
                logging.warning('Duplicate alias %s. Dropping' % unique_path)

    def write(self, filename: str) -> None:
        with zipfile.ZipFile(filename, mode='w', compression=self.COMPRESSION_TYPE) as outzip:
            outzip.writestr(self.firmwareid_filename, self.firmwareid.hex())
            outzip.writestr(self.metadata_filename, json.dumps(self.metadata, indent=4))
            outzip.writestr(self.varmap_filename, self.varmap.get_json())
            outzip.writestr(self.alias_file, self.serialize_aliases(list(self.aliases.values())))

    @classmethod
    def serialize_aliases(cls, aliases:Union[Dict[str, AliasDefinition], List[AliasDefinition]]) -> bytes:
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
    
    def get_aliases_for_datastore(self) -> Generator[Tuple[str, AliasDefinition], None, None]:
        for k in self.aliases:
            yield (self.aliases[k].get_fullpath(), self.aliases[k])

    def get_aliases(self) -> Dict[str, AliasDefinition]:
        return self.aliases

    def get_metadata(self):
        return self.metadata

    @classmethod
    def firmware_id_length(cls) -> int:
        return len(firmware_id.PLACEHOLDER)
