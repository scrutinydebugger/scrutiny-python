from enum import Enum


class VariableLocation:
    def __init__(self, address):
        if not isinstance(address, int):
            raise ValueError('Address must be a valid integer')

        self.address = address

    def get_address(self):
        return self.address

    @classmethod
    def check_endianness(cls, endianness):
        if endianness not in ['little', 'big']:
            raise ValueError('Invalid endianness "%s" ' % endianness)

    @classmethod
    def from_bytes(cls, data, endianness):
        if isinstance(data, list):
            data = bytes(data)
        if not isinstance(data, bytes):
            raise ValueError('Data must be bytes, not %s' % (data.__class__.__name__))

        if len(data) < 1:
            raise ValueError('Empty data')

        cls.check_endianness(endianness)
        address = int.from_bytes(data, byteorder=endianness, signed=False)
        return cls(address)

    def copy(self):
        return VariableLocation(self.get_address())

    def __str(self):
        return str(self.get_address())

    def __repr__(self):
        return '<%s - 0x%08X>' % (self.__class__.__name__, self.get_address())

class VariableType(Enum):
    sint8 = 0
    uint8 = 1
    sint16 = 2
    uint16 = 3
    sint32 = 4
    uint32 = 5
    sint64 = 6
    uint64 = 7
    float32 = 8
    float64 = 9
    boolean = 10
    struct = 11

    def get_size_bit(self):
        sizemap = {
            self.__class__.sint8 : 8,
            self.__class__.uint8 : 8,
            self.__class__.sint16 : 16,
            self.__class__.uint16 : 16,
            self.__class__.sint32 : 32,
            self.__class__.uint32 : 32,
            self.__class__.sint64 : 64,
            self.__class__.uint64 : 64,
            self.__class__.float32 : 32,
            self.__class__.float64 : 64,
            self.__class__.boolean : 8,
            self.__class__.struct  : None
        }

        return sizemap[self]


class Variable:
    def __init__(self, name, vartype_id, vartype, path_segments, location, endianness,  bitsize=None, bitoffset=None, enum=None):
        self.name = name
        self.vartype_id = vartype_id
        self.vartype = vartype
        self.path_segments = path_segments
        self.location = location
        self.endianness = endianness
        self.bitsize = bitsize
        self.bitoffset = bitoffset
        self.enum=enum   


    def get_fullname(self):
        if len(self.path_segments) == 0:
            path_str = '/'
        else:
            path_str = '/'+'/'.join(self.path_segments)
        return  '%s/%s' % (path_str, self.name)

    def get_type(self):
        return self.vartype

    def get_path_segments(self):
        return self.path_segments

    def get_address(self):
        return self.location.get_address()

    def get_def(self):
        desc = {
            'addr' : self.get_address(),
            'type_id' : self.vartype_id
        }

        if self.bitsize is not None:
            desc['bitsize'] = self.bitsize

        if self.bitoffset is not None:
            desc['bitoffset'] = self.bitoffset

        if self.enum is not None:
            desc['enum_id'] = self.enum.get_id()

        return desc


    def __repr__(self):
        return '<%s - %s (%s) @ %s>' % (self.__class__.__name__, self.get_fullname(), self.vartype, self.location)

class VariableEnum:
    UNIQUE_ID = 0

    def __init__(self, name):
        self.name = name
        self.vals = {}
        self.unique_id = self.UNIQUE_ID
        self.UNIQUE_ID+=1

    def set_id(self, unique_id):
        self.unique_id = unique_id
        if self.unique_id > self.UNIQUE_ID:
            self.UNIQUE_ID = self.unique_id+1

    def add_value(self, value, name):
        if value in self.vals and self.vals[value] != name:
            raise Exception('Duplicate entry for enum %s. %s can either be %s or %s' % (self.name, value, self.vals[value], name))
        self.vals[value] = name

    def get_name(self, value):
        if value not in self.vals:
            return None
        return self.vals[value]

    def get_id(self):
        return self.unique_id

    def get_def(self):
        obj = {
            'name' : self.name,
            'values' : self.vals
        }
        return obj

    @classmethod
    def from_def(cls, enum_id, enum_def):
        obj = cls(enum_def['name'])
        obj.vals = {}
        for k in enum_def['values']:
            if isinstance(k, str):
                newkey = int(k)
            else:
                newkey = k
            obj.vals[newkey] = enum_def['values'][k]
        obj.set_id(enum_id)
        return obj

class Struct:
    class Member:
        def __init__(self, name, vartype, vartype_id=None, bitoffset=None, bitsize=None, substruct=None):

            if not isinstance(vartype, VariableType):
                raise ValueError('vartype must be an instance of VariableType')

            if bitoffset is not None:
                if not isinstance(bitoffset, int):
                    raise ValueError('bitoffset must be an integer value')
                if bitoffset < 0:
                    raise ValueError('bitoffset must be a positive integer')

            if bitsize is not None:
                if not isinstance(bitsize, int):
                    raise ValueError('bitsize must be an integer value')
                if bitsize < 0:
                    raise ValueError('bitsize must be a positive integer')                 

            if substruct is not None:
                if not isinstance(substruct, Struct):
                    raise ValueError('substruct must be Struct instance')

            self.name = name
            self.vartype = vartype
            self.bitoffset = bitoffset
            self.bitsize = bitsize
            self.substruct = substruct
            self.vartype_id = vartype_id

    def __init__(self, name):
        self.name = name
        self.members = {}

    def add_member(self, member):
        if member.name in self.members:
            raise Exception('Duplicate member %s' % member.name)

        if not isinstance(member, Struct) and not isinstance(member, Struct.Member):
            raise ValueError('Node must be a member or a substruct')

        self.members[member.name] = member
       