from enum import Enum

from typing import Union, Optional, Dict

class Endianness(Enum):
    Little = 0
    Big = 1

class DataTypeType(Enum):
    _sint = (0 << 4)
    _uint = (1 << 4)
    _float = (2 << 4)
    _boolean = (3 << 4)
    _cfloat = (4 << 4)
    _struct = (5 << 4)

class DataTypeSize(Enum):
    _8 = 0
    _16 = 1
    _32 = 2
    _64 = 3
    _128 = 4
    _256 = 5
    _NA = 0xF    

class EmbeddedDataType(Enum):
    sint8 = DataTypeType._sint.value | DataTypeSize._8.value
    sint16 = DataTypeType._sint.value | DataTypeSize._16.value
    sint32 = DataTypeType._sint.value | DataTypeSize._32.value
    sint64 = DataTypeType._sint.value | DataTypeSize._64.value
    sint128 = DataTypeType._sint.value | DataTypeSize._128.value
    sint256 = DataTypeType._sint.value | DataTypeSize._256.value
    
    uint8 = DataTypeType._uint.value | DataTypeSize._8.value
    uint16 = DataTypeType._uint.value | DataTypeSize._16.value
    uint32 = DataTypeType._uint.value | DataTypeSize._32.value
    uint64 = DataTypeType._uint.value | DataTypeSize._64.value
    uint128 = DataTypeType._uint.value | DataTypeSize._128.value
    uint256 = DataTypeType._uint.value | DataTypeSize._256.value
    
    float8 = DataTypeType._float.value | DataTypeSize._8.value
    float16 = DataTypeType._float.value | DataTypeSize._16.value
    float32 = DataTypeType._float.value | DataTypeSize._32.value
    float64 = DataTypeType._float.value | DataTypeSize._64.value
    float128 = DataTypeType._float.value | DataTypeSize._128.value
    float256 = DataTypeType._float.value | DataTypeSize._256.value
    
    cfloat8 = DataTypeType._cfloat.value | DataTypeSize._8.value
    cfloat16 = DataTypeType._cfloat.value | DataTypeSize._16.value
    cfloat32 = DataTypeType._cfloat.value | DataTypeSize._32.value
    cfloat64 = DataTypeType._cfloat.value | DataTypeSize._64.value
    cfloat128 = DataTypeType._cfloat.value | DataTypeSize._128.value
    cfloat256 = DataTypeType._cfloat.value | DataTypeSize._256.value
    
    boolean = DataTypeType._boolean.value | DataTypeSize._8.value
    
    struct = DataTypeType._struct.value | DataTypeSize._NA.value

    def get_size_bit(self) -> Optional[int]:
        v = self.get_size_byte()
        if v is None:
            return None
        return v*8

    def get_size_byte(self) -> Optional[int]:
        vbytes = (self.value & 0xF)
        if vbytes == 0xF:
            return None
        return 1 << vbytes

class RuntimePublishedValue:
    id:int
    datatype:EmbeddedDataType

    def __init__(self, id:int, datatype:Union[EmbeddedDataType, int]):
        if id < 0 or id > 0xFFFF:
            raise ValueError('RuntimePublishedValue ID out of range (0x0000-0xFFFF). %d' % id)
        
        if isinstance(datatype, int):
            datatype = EmbeddedDataType(datatype)
        
        self.id = id
        self.datatype = datatype
