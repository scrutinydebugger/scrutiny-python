#    varmap.py
#        A VarMap list all variables in a firmware file along with their types, address, bit
#        offset, etc
#        . I is a simplified version of the DWARF debugging symbols.
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import json
import os

from scrutiny.core import Variable, VariableType, VariableEnum


class VarMap:
    def __init__(self, file=None):
        error = None
        if file is not None:
            try:
                if os.path.isfile(file):
                    with open(file, 'r') as f:
                        content = json.loads(f.read())
                else:
                    content = json.loads(file)

                self.validate_json(content)

                self.endianness = content['endianness']
                self.typemap = content['type_map']
                self.variables = content['variables']
                self.enums = content['enums']
            except Exception as e:
                error = e

            if error is not None:
                raise Exception('Error loading VarMap - %s: %s' % (type(error).__name__, str(error)))

        else:
            self.endianness = 'little'
            self.typemap = {}
            self.variables = {}
            self.enums = {}

        self.validate()  # Validate only if loaded. Otherwise, we may be building a new varmap file (from CLI)
        self.init_all()

    def init_all(self):
        self.next_type_id = 0
        self.next_enum_id = 0
        self.typename2typeid_map = {}   # Maps the type id of this VarMap to the original name inside the binary.
        self.enums_to_id_map = {}       # Maps a VariableEnum object to it's internal id

        # Build typename2typeid_map
        for typeid in self.typemap:
            typeid = int(typeid)
            if typeid > self.next_type_id:
                self.next_type_id = typeid

            typename = self.typemap[str(typeid)]['name']
            self.typename2typeid_map[typename] = typeid

        # Build enums_to_id_map
        for enum_id in self.enums:
            enum_id = int(enum_id)
            if enum_id > self.next_enum_id:
                self.next_enum_id = enum_id

            enum = VariableEnum.from_def(self.enums[str(enum_id)])
            self.enums_to_id_map[enum] = enum_id

    def set_endianness(self, endianness):
        if endianness not in ['little', 'big']:
            raise ValueError('Invalid endianness %s' % endianness)
        self.endianness = endianness

    def write(self, filename):
        with open(filename, 'w') as f:
            f.write(self.get_json())

    def get_json(self):
        content = {
            'endianness': self.endianness,
            'type_map': self.typemap,
            'variables': self.variables,
            'enums': self.enums,
        }
        return json.dumps(content, indent=4)

    def validate(self):
        pass

    def validate_json(self, content):
        required_fields = {
            'endianness',
            'type_map',
            'variables',
            'enums'
        }

        for field in required_fields:
            if field not in content:
                raise Exception('Missing field "%s"' % field)

    def add_variable(self, path_segments, name, location, original_type_name, bitsize=None, bitoffset=None, enum=None):
        if not self.is_known_type(original_type_name):
            raise ValueError('Cannot add variable of type %s. Type has not been registered yet' % (original_type_name))

        fullname = self.make_fullname(path_segments, name)
        if fullname in self.variables:
            logging.warning('duplicate entry %s' % fullname)

        entry = dict(
            type_id=self.get_type_id(original_type_name),
            addr=location.get_address(),
        )

        if bitoffset is not None:
            entry['bitoffset'] = bitoffset

        if bitsize is not None:
            entry['bitsize'] = bitsize

        if enum is not None:
            if enum not in self.enums_to_id_map:
                self.enums[self.next_enum_id] = enum.get_def()
                self.enums_to_id_map[enum] = self.next_enum_id
                self.next_enum_id += 1

            entry['enum_id'] = self.enums_to_id_map[enum]

        self.variables[fullname] = entry

    def register_base_type(self, original_name, vartype):
        if not isinstance(vartype, VariableType):
            raise ValueError('Given vartype must be an instance of VariableType')

        if self.is_known_type(original_name):
            assigned_vartype = self.get_vartype_from_binary_name(original_name)
            if assigned_vartype != vartype:
                raise Exception('Cannot assign type %s to  "%s". Scrutiny type already assigned: %s' % (vartype, original_name, assigned_vartype))
        else:
            typeid = self.next_type_id
            self.next_type_id += 1
            self.typename2typeid_map[original_name] = typeid
            self.typemap[typeid] = dict(name=original_name, type=vartype.name)

    def get_vartype_from_binary_name(self, binary_type_name):
        typeid = self.typename2typeid_map[binary_type_name]
        vartype_name = self.typemap[typeid]['type']
        return VariableType[vartype_name]    # Enums supports square brackets to get enum from name

    def has_type_id(self, typeid):
        return (typeid in self.typemap)

    def is_known_type(self, binary_type_name):
        return (binary_type_name in self.typename2typeid_map)

    def get_type_id(self, binary_type_name):
        if binary_type_name not in self.typename2typeid_map:
            raise Exception('Type name %s does not exist in the Variable Description File' % (binary_type_name))

        return self.typename2typeid_map[binary_type_name]

    def get_var(self, fullname):
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

    def make_segments(self, fullname):
        pieces = fullname.split('/')
        segments = [segment for segment in pieces[0:-1] if segment]
        name = pieces[-1]
        return (segments, name)

    def make_fullname(self, path_segments, name):
        fullname = '/'
        for segment in path_segments:
            fullname += segment + '/'
        fullname += name
        return fullname

    def get_type(self, vardef):
        type_id = str(vardef['type_id'])
        if type_id not in self.typemap:
            raise AssertionError('Variable %s refer to a type not in type map' % fullname)
        typename = self.typemap[type_id]['type']
        return VariableType.__getattr__(typename)

    def get_addr(self, vardef):
        return vardef['addr']

    def get_var_def(self, fullname):
        if fullname not in self.variables:
            raise ValueError('%s not in Variable Decsription File' % fullname)
        return self.variables[fullname]

    def get_bitsize(self, vardef):
        if 'bitsize' in vardef:
            return vardef['bitsize']

    def get_bitoffset(self, vardef):
        if 'bitoffset' in vardef:
            return vardef['bitoffset']

    def get_enum(self, vardef):
        if 'enum_id' in vardef:
            enum_id = str(vardef['enum_id'])
            if enum_id not in self.enums:
                raise Exception("Unknown enum_id %s" % enum_id)
            enum_def = self.enums[enum_id]
            return VariableEnum.from_def(enum_def)
