from enum import Enum
import struct


MASK_MAP = {}
for i in range(63):
    v = 0
    for j in range(i):
        v |= (1 << j)
        MASK_MAP[i] = v

class VariableLocation:
    def __init__(self, address):
        if not isinstance(address, int):
            raise ValueError('Address must be a valid integer')

        self.address = address

    def get_address(self):
        return self.address

    def add_offset(self, offset):
        self.address += offset

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
    sint16 = 1
    sint32 = 2
    sint64 = 3
    sint128 = 4
    sint256 = 5
    uint8 = 10
    uint16 = 11
    uint32 = 12
    uint64 = 13
    uint128 = 14
    uint256 = 15    
    float8 = 20
    float16 = 21
    float32 = 22
    float64 = 23
    float128 = 24
    float256 = 25
    cfloat8 = 30
    cfloat16 = 31
    cfloat32 = 32
    cfloat64 = 33
    cfloat128 = 34
    cfloat256 = 35
    boolean = 40
    struct = 41

    def get_size_bit(self):
        sizemap = {
            self.__class__.sint8 : 8,
            self.__class__.uint8 : 8,
            self.__class__.float8 : 8,
            self.__class__.cfloat8 : 8,
        
            self.__class__.sint16 : 16,
            self.__class__.uint16 : 16,
            self.__class__.float16 : 16,
            self.__class__.cfloat16 : 16,

            self.__class__.sint32 : 32,
            self.__class__.uint32 : 32,
            self.__class__.float32 : 32,
            self.__class__.cfloat32 : 32,

            self.__class__.sint64 : 64,
            self.__class__.uint64 : 64,
            self.__class__.float64 : 64,
            self.__class__.cfloat64 : 64,

            self.__class__.sint128 : 128,
            self.__class__.uint128 : 128,
            self.__class__.float128 : 128,
            self.__class__.cfloat128 : 128,

            self.__class__.sint256 : 256,
            self.__class__.uint256 : 256,
            self.__class__.float256 : 256,
            self.__class__.cfloat256 : 256,

            self.__class__.boolean : 8,
            self.__class__.struct  : None
        }

        return sizemap[self]


class Variable:

    class BaseDecoder:
        def __init__(self):
            pass

    class SIntDecoder(BaseDecoder):
        str_map = {
                1 : 'b',
                2 : 'h',
                4 : 'l',
                8 : 'q'
            }

        def __init__(self, size):
            super().__init__()
            if size not in self.str_map:
                raise NotImplementedError('Does not support signed int of %d bytes', size)
            self.str = self.str_map[size]


        def decode(self, data, endianness):
            endianness_char = '<' if endianness == 'little' else '>'
            return struct.unpack(endianness_char+self.str, data)[0]

    class UIntDecoder(BaseDecoder):
        str_map = {
                1 : 'B',
                2 : 'H',
                4 : 'L',
                8 : 'Q'
            }

        def __init__(self, size):
            super().__init__()
            if size not in self.str_map:
                raise NotImplementedError('Does not support signed int of %d bytes', size)
            self.str = self.str_map[size]

        def decode(self, data, endianness):
            endianness_char = '<' if endianness == 'little' else '>'
            return struct.unpack(endianness_char+self.str, data)[0]

    class FloatDecoder(BaseDecoder):
        str_map = {
            4 : 'f',
            8 : 'd'
        }

        def __init__(self, size):
            super().__init__()
            if size not in self.str_map:
                raise NotImplementedError('Does not support float of %d bytes', size)
            self.str = self.str_map[size]

        def decode(self, data, endianness):
            endianness_char = '<' if endianness == 'little' else '>'
            return struct.unpack(endianness_char+self.str, data)[0]

    class BoolDecoder(BaseDecoder):
        def __init__(self):
            super().__init__()

        def decode(self, data, endianness,):
            return True if data[0] != 0 else False

    class NotImplementedDecoder:
        def __init__(self, type_name):
            self.type_name = type_name

        def decode(self, data, endianness):
            raise NotImplementedError('Decoding data for type %s is not supported yet' % self.type_name)

    TYPE_TO_DECODER_MAP = {
            VariableType.sint8 : SIntDecoder(1),
            VariableType.sint16 : SIntDecoder(2),
            VariableType.sint32 : SIntDecoder(4),
            VariableType.sint64 : SIntDecoder(8),
            VariableType.sint128 : NotImplementedDecoder(VariableType.sint128.name),
            VariableType.sint256 : NotImplementedDecoder(VariableType.sint256.name),

            VariableType.uint8 : UIntDecoder(1),
            VariableType.uint16 : UIntDecoder(2),
            VariableType.uint32 : UIntDecoder(4),
            VariableType.uint64 : UIntDecoder(8),
            VariableType.uint128 : NotImplementedDecoder(VariableType.uint128.name),
            VariableType.uint256 : NotImplementedDecoder(VariableType.uint256.name),

            VariableType.float8 : NotImplementedDecoder(VariableType.float8.name),
            VariableType.float16 : NotImplementedDecoder(VariableType.float16.name),
            VariableType.float32 : FloatDecoder(4),
            VariableType.float64 : FloatDecoder(8),
            VariableType.float128 : NotImplementedDecoder(VariableType.float128.name),
            VariableType.float256 : NotImplementedDecoder(VariableType.float256.name),

            VariableType.cfloat8 : NotImplementedDecoder(VariableType.cfloat8.name),
            VariableType.cfloat16 : NotImplementedDecoder(VariableType.cfloat16.name),
            VariableType.cfloat32 : NotImplementedDecoder(VariableType.cfloat32.name),
            VariableType.cfloat64 : NotImplementedDecoder(VariableType.cfloat64.name),
            VariableType.cfloat128 : NotImplementedDecoder(VariableType.cfloat128.name),
            VariableType.cfloat256 : NotImplementedDecoder(VariableType.cfloat256.name),

            VariableType.boolean : BoolDecoder(),
    }


    def __init__(self, name,  vartype, path_segments, location, endianness,  bitsize=None, bitoffset=None, enum=None): 

        self.name = name
        self.vartype = vartype
        self.path_segments = path_segments
        if isinstance(location, VariableLocation):
            self.location = location.copy()
        else:
            self.location = VariableLocation(location)
        self.endianness = endianness

        if bitoffset is not None and bitsize is None:
            bitsize = self.vartype.get_size_bit() - bitoffset
        elif bitoffset is None and bitsize is not None:
            bitoffset = 0
        self.bitfield  = False if bitoffset is None and bitsize is None else True
        self.bitsize = bitsize
        self.bitoffset = bitoffset
        self.enum=enum   

    def decode(self, data):
        decoded = self.TYPE_TO_DECODER_MAP[self.vartype].decode(data, self.endianness)
        if self.bitfield:
            decoded >>= self.bitoffset
            decoded &= MASK_MAP[self.bitsize]
        return decoded

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

    def get_size(self):
        return int(self.vartype.get_size_bit()/8)

    def __repr__(self):
        return '<%s - %s (%s) @ %s>' % (self.__class__.__name__, self.get_fullname(), self.vartype, self.location)

class VariableEnum:

    def __init__(self, name):
        self.name = name
        self.vals = {}

    def add_value(self, value, name):
        if value in self.vals and self.vals[value] != name:
            raise Exception('Duplicate entry for enum %s. %s can either be %s or %s' % (self.name, value, self.vals[value], name))
        self.vals[value] = name

    def get_name(self, value):
        if value not in self.vals:
            return None
        return self.vals[value]

    def get_def(self):
        obj = {
            'name' : self.name,
            'values' : self.vals
        }
        return obj

    @classmethod
    def from_def(cls, enum_def):
        obj = cls(enum_def['name'])
        obj.vals = {}
        for k in enum_def['values']:
            if isinstance(k, str):
                newkey = int(k)
            else:
                newkey = k
            obj.vals[newkey] = enum_def['values'][k]
        return obj

class Struct:
    class Member:
        def __init__(self, name, is_substruct=False, original_type_name=None, byte_offset=None, bitoffset=None, bitsize=None, substruct=None):

            if not is_substruct:
                if original_type_name is None:
                    raise ValueError('A typename must be given for non-struct member')

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

            if byte_offset is not None:
                if not isinstance(byte_offset, int):
                    raise ValueError('byte_offset must be an integer value')
                if byte_offset < 0:
                    raise ValueError('byte_offset must be a positive integer')                 

            if substruct is not None:
                if not isinstance(substruct, Struct):
                    raise ValueError('substruct must be Struct instance')

            self.name = name
            self.is_substruct = is_substruct
            self.original_type_name = original_type_name
            self.bitoffset = bitoffset
            self.byte_offset = byte_offset
            self.bitsize = bitsize
            self.substruct = substruct

    def __init__(self, name):
        self.name = name
        self.members = {}

    def add_member(self, member):
        if member.name in self.members:
            raise Exception('Duplicate member %s' % member.name)

        if not isinstance(member, Struct) and not isinstance(member, Struct.Member):
            raise ValueError('Node must be a member or a substruct')

        self.members[member.name] = member
       