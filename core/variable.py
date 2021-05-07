from enum import Enum




class DwarfEncoding(Enum):
    DW_ATE_address         = 0x1
    DW_ATE_boolean         = 0x2
    DW_ATE_complex_float   = 0x3
    DW_ATE_float           = 0x4
    DW_ATE_signed          = 0x5
    DW_ATE_signed_char     = 0x6
    DW_ATE_unsigned        = 0x7
    DW_ATE_unsigned_char   = 0x8
    DW_ATE_lo_user         = 0x80
    DW_ATE_hi_user         = 0xff

class VariableLocation:
    def __init__(self, data, endianness):
        if isinstance(data, list):
            data = bytes(data)
        if not isinstance(data, bytes):
            raise ValueError('Data must be bytes, not %s' % (data.__class__.__name__))

        if len(data) < 1:
            raise ValueError('Empty data')
        self.check_endianness(endianness)

        self.data = data
        self.endianness = endianness

    @classmethod
    def check_endianness(cls, endianness):
        if endianness not in ['little', 'big']:
            raise ValueError('Invalid endianness "%s" ' % endianness)

    @classmethod
    def from_int(cls, val, endianness):
        if not isinstance(val, int):
            raise ValueError('Value must be a valid integer')
        cls.check_endianness(endianness)
        return cls(val.tobytes(endianness), endianness)

    @classmethod
    def from_bytes(cls, data, endianness):
        return cls(data, endianness)

    def decode(self):
        return int.from_bytes(self.data, byteorder=self.endianness, signed=False)

    def __str(self):
        return str(self.decode())

    def __repr__(self):
        return '<%s - 0x%08X>' % (self.__class__.__name__, self.decode())

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


class Variable:
    def __init__(self, name, vartype_id, vartype, path_segments, location, endianness, bitwidth=None, bitoffset=None, enum=None):
        self.name = name
        self.vartype_id = vartype_id
        self.vartype = vartype
        self.path_segments = path_segments
        self.location = location
        self.endianness = endianness
        self.bitwidth = bitwidth
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

    def get_def(self):
        desc = {
            'location' : self.location.decode(),
            'type_id' : self.vartype_id
        }
        if self.bitwidth is not None:
            desc['bitwidth'] = self.bitwidth

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