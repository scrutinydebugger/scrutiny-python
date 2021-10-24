import json
from . import Variable, VariableType, VariableEnum
import os

class VarDesc:
    def __init__(self, file):
        error = None
        try:
            if os.path.isfile(file):
                with open(file, 'r') as f:
                    self.content = json.loads(f.read())
            else:
                self.content = json.loads(file)

            if 'endianness' not in self.content:
                raise Exception('Missing endianness')

            self.endianness = self.content['endianness']
        except Exception as e:
            error = e

        if error is not None:
            raise Exception('Error loading VarDesc (%s) - %s: %s' % (file, type(error).__name__, str(error)))

    def get_json(self):
        return json.dumps(self.content, indent=4)

    def validate(self):
        pass


    def get_var(self, fullname):
        segments, name = self.make_segments(fullname)
        vardef = self.get_var_def(fullname)

        return Variable(
            name            = name, 
            vartype_id      = self.get_type_id(vardef), 
            vartype         = self.get_type(vardef), 
            path_segments   = segments, 
            location        = self.get_addr(vardef), 
            endianness      = self.endianness, 
            bitsize         = self.get_bitsize(vardef), 
            bitoffset       = self.get_bitoffset(vardef), 
            enum            = self.get_enum(vardef)
            )

    def make_segments(self, fullname):
        pieces = fullname.split('/')
        segments = [segment for segment in pieces[0:-1] if segment]
        name = pieces[-1]
        return (segments, name)

    def get_type_id(self, vardef):
        return vardef['type_id']

    def get_type(self, vardef):
        type_id = str( vardef['type_id'])
        if type_id not in self.content['type_map']:
            raise AssertionError('Variable %s refer to a type not in type map' % fullname )
        typename = self.content['type_map'][type_id]['type']
        return VariableType.__getattr__(typename)

    def get_addr(self, vardef):
        return vardef['addr']

    def get_var_def(self, fullname):
        if fullname not in self.content['variables']:
            raise ValueError('%s not in Variable Decsription File' % fullname)
        return self.content['variables'][fullname]

    def get_bitsize(self, vardef):
        if 'bitsize' in vardef:
            return vardef['bitsize']

    def get_bitoffset(self, vardef):
        if 'bitoffset' in vardef:
            return vardef['bitoffset']

    def get_enum(self, vardef):
        if 'enum_id' in vardef:
            enum_id = str(vardef['enum_id'])
            if enum_id not in self.content['enums']:
                raise Exception("Unknown enum_id %s" % enum_id)
            enum_def = self.content['enums'][enum_id]
            return VariableEnum.from_def(int(enum_id), enum_def)

