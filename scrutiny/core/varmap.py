#    varmap.py
#        A VarMap list all variables in a firmware file along with their types, address, bit
#        offset, etc
#        . I is a simplified version of the DWARF debugging symbols.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import json
import os
import logging

from scrutiny.core.variable import Variable, VariableEnum, VariableLocation
from scrutiny.core.basic_types import EmbeddedDataType, Endianness
from typing import Dict, TypedDict, List, Tuple, Optional, Any, Union, Generator
from scrutiny.core.variable import VariableEnumDef


class TypeEntry(TypedDict):
    name: str
    type: str


class VariableEntry(TypedDict, total=False):
    type_id: str  # integer as string because of json format that can't have a dict key as int
    addr: int
    bitoffset: int
    bitsize: int
    enum: int


# TODO : This class requires more work and unit tests
class VarMap:
    logger: logging.Logger
    endianness: Endianness
    typemap: Dict[str, TypeEntry]
    variables: Dict[str, VariableEntry]
    enums: Dict[str, VariableEnumDef]

    next_type_id: int
    next_enum_id: int
    typename2typeid_map: Dict[str, str]      # name to numeric id as string
    enums_to_id_map: Dict[VariableEnum, int]

    def __init__(self, file: Optional[Union[str, bytes]] = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        error = None
        if file is not None:
            try:
                if os.path.isfile(file):
                    with open(file, 'r') as f:
                        content = json.loads(f.read())
                else:
                    if isinstance(file, bytes):
                        file = file.decode('utf8')
                    content = json.loads(file)

                self.validate_json(content)

                if content['endianness'].lower().strip() == 'little':
                    self.endianness = Endianness.Little
                elif content['endianness'].lower().strip() == 'big':
                    self.endianness = Endianness.Big
                else:
                    raise Exception('Unknown endianness %s' % content['endianness'])

                self.typemap = content['type_map']
                self.variables = content['variables']
                self.enums = content['enums']
            except Exception as e:
                error = e

            if error is not None:
                raise Exception('Error loading VarMap - %s: %s' % (type(error).__name__, str(error)))

        else:
            self.endianness = Endianness.Little
            self.typemap = {}
            self.variables = {}
            self.enums = {}

        self.validate()  # Validate only if loaded. Otherwise, we may be building a new varmap file (from CLI)
        self.init_all()

    def init_all(self) -> None:
        self.next_type_id = 0
        self.next_enum_id = 0
        self.typename2typeid_map = {}   # Maps the type id of this VarMap to the original name inside the binary.
        self.enums_to_id_map = {}       # Maps a VariableEnum object to it's internal id

        # Build typename2typeid_map
        for typeid_str in self.typemap:
            typeid_int = int(typeid_str)
            if typeid_int > self.next_type_id:
                self.next_type_id = typeid_int

            typename = self.typemap[str(typeid_int)]['name']
            self.typename2typeid_map[typename] = typeid_str

        # Build enums_to_id_map
        for enum_id_str in self.enums:
            enum_id_int = int(enum_id_str)
            if enum_id_int > self.next_enum_id:
                self.next_enum_id = enum_id_int

            enum = VariableEnum.from_def(self.enums[str(enum_id_int)])
            self.enums_to_id_map[enum] = enum_id_int

    def set_endianness(self, endianness: Endianness) -> None:
        if endianness not in [Endianness.Little, Endianness.Big]:
            raise ValueError('Invalid endianness %s' % endianness)
        self.endianness = endianness

    def get_endianness(self) -> Endianness:
        return self.endianness

    def write(self, filename: str) -> None:
        with open(filename, 'w') as f:
            f.write(self.get_json())

    def get_json(self) -> str:
        if self.endianness == Endianness.Little:
            endianness_str = 'little'
        elif self.endianness == Endianness.Big:
            endianness_str = 'big'
        else:
            raise Exception('Unknown endianness')

        content = {
            'endianness': endianness_str,
            'type_map': self.typemap,
            'variables': self.variables,
            'enums': self.enums,
        }
        return json.dumps(content, indent=4)

    def validate(self) -> None:
        pass

    def validate_json(self, content: Dict[str, Any]) -> None:
        required_fields = {
            'endianness',
            'type_map',
            'variables',
            'enums'
        }

        for field in required_fields:
            if field not in content:
                raise Exception('Missing field "%s"' % field)

    def add_variable(self,
                     path_segments: List[str],
                     name: str,
                     location: VariableLocation,
                     original_type_name: str,
                     bitsize: Optional[int] = None,
                     bitoffset: Optional[int] = None,
                     enum: Optional[VariableEnum] = None
                     ) -> None:
        if not self.is_known_type(original_type_name):
            raise ValueError('Cannot add variable of type %s. Type has not been registered yet' % (original_type_name))

        fullname = self.make_fullname(path_segments, name)
        if fullname in self.variables:
            self.logger.warning('duplicate entry %s' % fullname)

        entry: VariableEntry = dict(
            type_id=self.get_type_id(original_type_name),
            addr=location.get_address(),
        )

        if bitoffset is not None:
            entry['bitoffset'] = bitoffset

        if bitsize is not None:
            entry['bitsize'] = bitsize

        if enum is not None:
            if enum not in self.enums_to_id_map:
                self.enums[str(self.next_enum_id)] = enum.get_def()
                self.enums_to_id_map[enum] = self.next_enum_id
                self.next_enum_id += 1

            entry['enum'] = self.enums_to_id_map[enum]

        self.variables[fullname] = entry

    def register_base_type(self, original_name: str, vartype: EmbeddedDataType) -> None:
        if not isinstance(vartype, EmbeddedDataType):
            raise ValueError('Given vartype must be an instance of EmbeddedDataType')

        if self.is_known_type(original_name):
            assigned_vartype = self.get_vartype_from_binary_name(original_name)
            if assigned_vartype != vartype:
                raise Exception('Cannot assign type %s to  "%s". Scrutiny type already assigned: %s' % (vartype, original_name, assigned_vartype))
        else:
            typeid = self.next_type_id
            self.next_type_id += 1
            self.typename2typeid_map[original_name] = str(typeid)
            self.typemap[str(typeid)] = dict(name=original_name, type=vartype.name)

    def get_vartype_from_binary_name(self, binary_type_name: str) -> EmbeddedDataType:
        typeid = self.typename2typeid_map[binary_type_name]
        vartype_name = self.typemap[typeid]['type']
        return EmbeddedDataType[vartype_name]    # Enums supports square brackets to get enum from name

    def is_known_type(self, binary_type_name: str) -> bool:
        return (binary_type_name in self.typename2typeid_map)

    def get_type_id(self, binary_type_name: str) -> str:
        if binary_type_name not in self.typename2typeid_map:
            raise Exception('Type name %s does not exist in the Variable Description File' % (binary_type_name))

        return self.typename2typeid_map[binary_type_name]   # Type is an integer as string

    def get_var(self, fullname: str) -> Variable:
        segments, name = self.make_segments(fullname)
        vardef = self.get_var_def(fullname)

        return Variable(
            name=name,
            vartype=self.get_type(vardef),
            path_segments=segments,
            location=self.get_addr(vardef),
            endianness=self.endianness,
            bitsize=self.get_bitsize(vardef),
            bitoffset=self.get_bitoffset(vardef),
            enum=self.get_enum(vardef)
        )

    def has_var(self, fullname: str) -> bool:
        return fullname in self.variables

    def make_segments(self, fullname: str) -> Tuple[List[str], str]:
        pieces = fullname.split('/')
        segments = [segment for segment in pieces[0:-1] if segment]
        name = pieces[-1]
        return (segments, name)

    def make_fullname(self, path_segments: List[str], name: str) -> str:
        fullname = '/'
        for segment in path_segments:
            fullname += segment + '/'
        fullname += name
        return fullname

    def get_type(self, vardef: VariableEntry) -> EmbeddedDataType:
        type_id = str(vardef['type_id'])
        if type_id not in self.typemap:
            raise AssertionError('Type "%s" refer to a type not in type map' % type_id)
        typename = self.typemap[type_id]['type']
        return EmbeddedDataType[typename]  # Enums support square brackets

    def get_addr(self, vardef: VariableEntry) -> int:
        return vardef['addr']

    def get_var_def(self, fullname: str) -> VariableEntry:
        if not self.has_var(fullname):
            raise ValueError('%s not in Variable Description File' % fullname)
        return self.variables[fullname]

    def get_bitsize(self, vardef: VariableEntry) -> Optional[int]:
        if 'bitsize' in vardef:
            return vardef['bitsize']
        return None

    def get_bitoffset(self, vardef: VariableEntry) -> Optional[int]:
        if 'bitoffset' in vardef:
            return vardef['bitoffset']
        return None

    def get_enum(self, vardef: VariableEntry) -> Optional[VariableEnum]:
        if 'enum' in vardef:
            enum_id = str(vardef['enum'])
            if enum_id not in self.enums:
                raise Exception("Unknown enum ID %s" % enum_id)
            enum_def = self.enums[enum_id]
            return VariableEnum.from_def(enum_def)
        return None

    def iterate_vars(self) -> Generator[Tuple[str, Variable], None, None]:
        for fullname in self.variables:
            yield (fullname, self.get_var(fullname))
