#    elf_dwarf_var_extractor.py
#        Reads a .elf file, extract the DWARF debugging symbols and make a VarMap object out
#        of it.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['ElfDwarfVarExtractor']

from elftools.elf.elffile import ELFFile
import os
from enum import Enum, auto
from .demangler import GccDemangler
import logging
import traceback
import inspect
from dataclasses import dataclass
from inspect import currentframe

from scrutiny.core.varmap import VarMap
from scrutiny.core.basic_types import *
from scrutiny.core.variable import *
from scrutiny.core.embedded_enum import *
from scrutiny.exceptions import EnvionmentNotSetUpException
from scrutiny.core.bintools import elftools_stubs

from typing import Optional, List, Dict, Union, cast, Set, Tuple

def get_linenumber() -> int:
    cf = currentframe()
    if cf is None:
        return -1
    if cf.f_back is None:
        return -1
    if cf.f_back.f_lineno is None:
        return -1

    return int(cf.f_back.f_lineno)

class TypeOfVar(Enum):
    BaseType=auto()
    Struct=auto()
    Class=auto()
    Union=auto()
    Pointer=auto()
    Array=auto()
    EnumOnly=auto() # Clang dwarf v2

@dataclass
class TypeDescriptor:
    type: TypeOfVar
    enum_die:Optional[ "elftools_stubs.Die"]
    type_die: "elftools_stubs.Die"

class ElfParsingError(Exception):
    pass


class CuName:
    """
    Handles a compile unit name. Useful to build a unique name as small as possible.
    """
    _class_internal_id = 0
    PATH_JOIN_CHAR = '_'

    cu: "elftools_stubs.CompileUnit"
    fullpath: str
    filename: str
    display_name: str
    segments: List[str]

    def __init__(self, cu: "elftools_stubs.CompileUnit", fullpath: str) -> None:
        self.cu = cu
        self.fullpath = os.path.normpath(fullpath)
        self.filename = os.path.basename(self.fullpath)
        self.display_name = self.filename
        self.segments = os.path.split(self.fullpath)[0].split(os.sep)

    def get_display_name(self) -> str:
        return self.display_name.replace('/', '-')

    def get_fullpath(self) -> str:
        return self.fullpath

    def go_up(self) -> None:
        """Add a the closest directory name to the display name.
        /aaa/bbb/ccc, ddd -->  /aaa/bbb, ccc_ddd"""
        if len(self.segments) > 0:
            last_dir = self.segments.pop()
            if last_dir == '':
                raise ElfParsingError('Cannot go up')
            self.display_name = self.PATH_JOIN_CHAR.join([last_dir, self.display_name])
        else:
            raise ElfParsingError('Cannot go up')

    def make_unique_numbered_name(self, name_set: Set[str]) -> str:
        i = 0
        while True:
            candidate = 'cu%d_%s' % (i, self.filename)
            if candidate not in name_set:
                return candidate
            i += 1


class ElfDwarfVarExtractor:
    defaults_names = {
        'DW_TAG_structure_type': '<struct>',
        'DW_TAG_enumeration_type': '<enum>',
        'DW_TAG_union_type': '<union>'
    }

    STATIC = 'static'
    GLOBAL = 'global'
    MAX_CU_DISPLAY_NAME_LENGTH = 40
    DW_OP_ADDR = 3
    DW_OP_plus_uconst = 0x23

    class DwarfEncoding(Enum):
        DW_ATE_address = 0x1
        DW_ATE_boolean = 0x2
        DW_ATE_complex_float = 0x3
        DW_ATE_float = 0x4
        DW_ATE_signed = 0x5
        DW_ATE_signed_char = 0x6
        DW_ATE_unsigned = 0x7
        DW_ATE_unsigned_char = 0x8
        DW_ATE_imaginary_float = 0x9
        DW_ATE_packed_decimal = 0xa
        DW_ATE_numeric_string = 0xb
        DW_ATE_edited = 0xc
        DW_ATE_signed_fixed = 0xd
        DW_ATE_unsigned_fixed = 0xe
        DW_ATE_decimal_float = 0xf
        DW_ATE_UTF = 0x10
        DW_ATE_lo_user = 0x80
        DW_ATE_hi_user = 0xff

    varmap: VarMap
    die2typeid_map: Dict["elftools_stubs.Die", str]
    die2vartype_map: Dict["elftools_stubs.Die", EmbeddedDataType]
    cu_name_map: Dict["elftools_stubs.CompileUnit", str]
    enum_die_map: Dict["elftools_stubs.Die", EmbeddedEnum]
    struct_die_map: Dict["elftools_stubs.Die", Struct]
    endianness: Endianness
    cppfilt: Optional[str]
    logger: logging.Logger

    def __init__(self, filename: Optional[str] = None, cppfilt: Optional[str] = None) -> None:
        self.varmap = VarMap()    # This is what we want to generate.
        self.die2typeid_map = {}
        self.die2vartype_map = {}
        self.cu_name_map = {}   # maps a CompileUnit object to it's unique display name
        self.enum_die_map = {}
        self.struct_die_map = {}
        self.endianness = Endianness.Little
        self.cppfilt = cppfilt
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self.logger.handlers
        self.initial_stack_depth= len(inspect.stack())

        if filename is not None:
            self.load_from_elf_file(filename)

    def make_name_for_log(self, die: Optional["elftools_stubs.Die"]) -> str:
        if die is None:
            return "<None>"
        name=''
        try:
            name = self.get_name(die, nolog=True)
        except:
            pass
        return f'{die.tag} <{die.offset:x}> "{name}"'

    def log_debug_process_die(self, die: "elftools_stubs.Die") -> None:
        if self.logger.isEnabledFor(logging.DEBUG):
            stack_depth = len(inspect.stack()) - self.initial_stack_depth-1
            stack_depth = max(stack_depth, 1)
            funcname = inspect.stack()[1][3]
            pad = '|  ' * (stack_depth - 1) + '|--'
            self.logger.debug(f"{pad}{funcname}({self.make_name_for_log(die)})")

    def get_varmap(self) -> VarMap:
        return self.varmap

    # Builds a dictionary that maps a CompuleUnit object to a unique displayable name
    def make_cu_name_map(self, dwarfinfo: "elftools_stubs.ELFFile") -> None:

        fullpath_cu_tuple_list = []
        fullpath_set = set()
        cu: "elftools_stubs.CompileUnit"
        for cu in dwarfinfo.iter_CUs():
            topdie: "elftools_stubs.Die" = cu.get_top_DIE()
            if topdie.tag != 'DW_TAG_compile_unit':
                raise ElfParsingError('Top die should be a compile unit')

            comp_dir = None
            name = self.get_name(topdie, 'unnamed_cu')
            if 'DW_AT_comp_dir' in topdie.attributes:
                comp_dir = topdie.attributes['DW_AT_comp_dir'].value.decode('utf8')
                fullpath = os.path.join(comp_dir, name)
            else:
                fullpath = os.path.abspath(name)

            if fullpath in fullpath_set:
                raise RuntimeError('Duplicate compile unit name')
            fullpath_set.add(fullpath)
            fullpath_cu_tuple_list.append((fullpath, cu))

        displayname_cu_tuple_list = self.make_unique_display_name(fullpath_cu_tuple_list)

        for item in displayname_cu_tuple_list:
            self.cu_name_map[item[1]] = item[0]

    @classmethod
    def make_unique_display_name(cls, fullpath_cu_tuple_list: List[Tuple[str, "elftools_stubs.CompileUnit"]]) -> List[Tuple[str, "elftools_stubs.CompileUnit"]]:
        displayname_map: Dict[str, List[CuName]] = {}

        for item in fullpath_cu_tuple_list:
            cuname = CuName(fullpath=item[0], cu=item[1])
            display_name = cuname.get_display_name()
            if display_name not in displayname_map:
                displayname_map[display_name] = []
            displayname_map[display_name].append(cuname)

        while True:
            duplicate_names = set()
            name_set = set()
            for display_name in displayname_map:
                name_set.add(display_name)
                if len(displayname_map[display_name]) > 1:
                    duplicate_names.add(display_name)

            if len(duplicate_names) == 0:
                break

            for display_name in duplicate_names:
                for cuname in displayname_map[display_name]:
                    try:
                        cuname.go_up()
                        newname = cuname.get_display_name()
                        if len(newname) > cls.MAX_CU_DISPLAY_NAME_LENGTH:
                            raise ElfParsingError('Name too long')
                    except Exception:
                        newname = cuname.make_unique_numbered_name(name_set)

                    name_set.add(newname)

                    if newname not in displayname_map:
                        displayname_map[newname] = []
                    displayname_map[newname].append(cuname)

                del displayname_map[display_name]

        displayname_cu_tuple_list: List[Tuple[str, "elftools_stubs.CompileUnit"]] = []
        for displayname in displayname_map:
            displayname_cu_tuple_list.append((displayname, displayname_map[displayname][0].cu))
        return displayname_cu_tuple_list

    def get_cu_name(self, die: "elftools_stubs.Die") -> str:
        return self.cu_name_map[die.cu]

    def get_die_at_spec(self, die: "elftools_stubs.Die") -> "elftools_stubs.Die":
        self.log_debug_process_die(die)
        refaddr = cast(int, die.attributes['DW_AT_specification'].value) + die.cu.cu_offset
        return die.dwarfinfo.get_DIE_from_refaddr(refaddr)
    
    def get_die_at_abstract_origin(self, die: "elftools_stubs.Die") -> "elftools_stubs.Die":
        self.log_debug_process_die(die)
        refaddr = cast(int, die.attributes['DW_AT_abstract_origin'].value) + die.cu.cu_offset
        return die.dwarfinfo.get_DIE_from_refaddr(refaddr)

    def get_name(self, die: "elftools_stubs.Die", default: Optional[str] = None, nolog:bool=False) -> str:
        if not nolog:
            self.log_debug_process_die(die)
        if 'DW_AT_name' in die.attributes:
            return cast(str, die.attributes['DW_AT_name'].value.decode('ascii'))
        else:
            if default is not None:
                return default
            elif die.tag in self.defaults_names:
                return self.defaults_names[die.tag]
            else:
                raise ElfParsingError('Cannot get a name for this die. %s' % die)

    def has_linkage_name(self, die: "elftools_stubs.Die") -> bool:
        if 'DW_AT_linkage_name' in die.attributes:
            return True
        if 'DW_AT_MIPS_linkage_name' in die.attributes:
            return True
        return False
    
    def get_linkage_name(self, die: "elftools_stubs.Die") -> str:
        self.log_debug_process_die(die)
        if 'DW_AT_linkage_name' in die.attributes:
            mangled_encoded = die.attributes['DW_AT_linkage_name'].value
        elif 'DW_AT_MIPS_linkage_name' in die.attributes:
            mangled_encoded = die.attributes['DW_AT_MIPS_linkage_name'].value
        else:
            raise ElfParsingError("No linkage name available")
        
        return self.demangler.demangle(mangled_encoded.decode('ascii'))

    def is_external(self, die: "elftools_stubs.Die") -> bool:
        """Tells if the die is accessible from outside the compile unit. If it is, it's global, otherwise it's static."""
        try:
            return cast(bool, die.attributes['DW_AT_external'].value)
        except Exception:
            return False

    def get_core_base_type(self, encoding: DwarfEncoding, bytesize: int) -> EmbeddedDataType:

        encoding_map: Dict["ElfDwarfVarExtractor.DwarfEncoding", Dict[int, EmbeddedDataType]] = {
            self.DwarfEncoding.DW_ATE_address: {
                # todo
            },
            self.DwarfEncoding.DW_ATE_boolean: {
                1: EmbeddedDataType.boolean
            },
            self.DwarfEncoding.DW_ATE_complex_float: {
                1: EmbeddedDataType.cfloat8,
                2: EmbeddedDataType.cfloat16,
                4: EmbeddedDataType.cfloat32,
                8: EmbeddedDataType.cfloat64,
                16: EmbeddedDataType.cfloat128,
                32: EmbeddedDataType.cfloat256
            },
            self.DwarfEncoding.DW_ATE_float: {
                1: EmbeddedDataType.float8,
                2: EmbeddedDataType.float16,
                4: EmbeddedDataType.float32,
                8: EmbeddedDataType.float64,
                16: EmbeddedDataType.float128,
                32: EmbeddedDataType.float256

            },
            self.DwarfEncoding.DW_ATE_signed: {
                1: EmbeddedDataType.sint8,
                2: EmbeddedDataType.sint16,
                4: EmbeddedDataType.sint32,
                8: EmbeddedDataType.sint64,
                16: EmbeddedDataType.sint128,
                32: EmbeddedDataType.sint256
            },
            self.DwarfEncoding.DW_ATE_signed_char: {
                1: EmbeddedDataType.sint8,
                2: EmbeddedDataType.sint16,
                4: EmbeddedDataType.sint32,
                8: EmbeddedDataType.sint64,
                16: EmbeddedDataType.sint128,
                32: EmbeddedDataType.sint256
            },
            self.DwarfEncoding.DW_ATE_unsigned: {
                1: EmbeddedDataType.uint8,
                2: EmbeddedDataType.uint16,
                4: EmbeddedDataType.uint32,
                8: EmbeddedDataType.uint64,
                16: EmbeddedDataType.uint128,
                32: EmbeddedDataType.uint256
            },
            self.DwarfEncoding.DW_ATE_unsigned_char: {
                1: EmbeddedDataType.uint8,
                2: EmbeddedDataType.uint16,
                4: EmbeddedDataType.uint32,
                8: EmbeddedDataType.uint64,
                16: EmbeddedDataType.uint128,
                32: EmbeddedDataType.uint256
            },
            self.DwarfEncoding.DW_ATE_UTF: {
                1: EmbeddedDataType.sint8,
                2: EmbeddedDataType.sint16,
                4: EmbeddedDataType.sint32,
            }
        }

        if encoding not in encoding_map:
            raise ValueError('Unknown encoding %s' % encoding)

        if bytesize not in encoding_map[encoding]:
            raise ValueError('Encoding %s with %d bytes' % (encoding, bytesize))

        return encoding_map[encoding][bytesize]

    def load_from_elf_file(self, filename: str) -> None:
        with open(filename, 'rb') as f:
            elffile = ELFFile(f)

            if not elffile.has_dwarf_info():
                raise ElfParsingError('File has no DWARF info')

            self.dwarfinfo = elffile.get_dwarf_info()
            self.endianness = Endianness.Little if elffile.little_endian else Endianness.Big

            self.make_cu_name_map(self.dwarfinfo)
            args = [self.cppfilt] if self.cppfilt is not None else []
            self.demangler = GccDemangler(*args)  # todo : adapt according to compile unit producer

            if not self.demangler.can_run():
                raise EnvionmentNotSetUpException("Demangler cannot be used. %s" % self.demangler.get_error())

            self.initial_stack_depth = len(inspect.stack())
            
            bad_support_warning_written = False
            for cu in self.dwarfinfo.iter_CUs():
                if cu.header['version'] not in (2,3,4):
                    if not bad_support_warning_written:
                        bad_support_warning_written = True
                        self.logger.warning(f"DWARF format version {cu.header['version']} is not well supported, output may be incomplete")
                die = cu.get_top_DIE()
                self.extract_var_recursive(die) # Recursion start point

    def extract_var_recursive(self, die: "elftools_stubs.Die") -> None:
        # Finds all "variable" tags and create an entry in the varmap.
        # Types / structures / enums are discovered as we go. We only take
        # definitions that are used by a variables, the rest will be ignored.

        self.log_debug_process_die(die)

        if die.tag == 'DW_TAG_variable':
            self.die_process_variable(die)  

        for child in die.iter_children():
            try:
                self.extract_var_recursive(child)
            except Exception as e:
                self.logger.error(f"Failed to extract var under {child}. {e}")
                self.logger.debug(traceback.format_exc()) 
    
    def get_typename_from_die(self, die: "elftools_stubs.Die") -> str:
        return cast(bytes, die.attributes['DW_AT_name'].value).decode('ascii')
    
    # Process die of type "base type". Register the type in the global index and maps it to a known type.
    def die_process_base_type(self, die: "elftools_stubs.Die") -> None:
        self.log_debug_process_die(die)
        name = self.get_typename_from_die(die)
        encoding = self.DwarfEncoding(cast(int, die.attributes['DW_AT_encoding'].value))
        bytesize = cast(int, die.attributes['DW_AT_byte_size'].value)
        basetype = self.get_core_base_type(encoding, bytesize)
        self.logger.debug(f"Registering base type: {name} as {basetype.name}")
        self.varmap.register_base_type(name, basetype)

        self.die2typeid_map[die] = self.varmap.get_type_id(name)
        self.die2vartype_map[die] = basetype

    def die_process_enum(self, die: "elftools_stubs.Die") -> None:
        self.log_debug_process_die(die)
        name = self.get_name(die)
        if die not in self.enum_die_map:
            enum = EmbeddedEnum(name)

            for child in die.iter_children():
                if child.tag != 'DW_TAG_enumerator':
                    continue

                name = self.get_name(child)
                if 'DW_AT_const_value' in child.attributes:
                    value = cast(int, child.attributes['DW_AT_const_value'].value)
                    enum.add_value(name=name, value=value)
                else:
                    self.logger.error('Enumerator without value')

            self.enum_die_map[die] = enum


    def extract_basetype_die(self, die: "elftools_stubs.Die") -> "elftools_stubs.Die":
        self.log_debug_process_die(die)
        basetype_die = self.get_first_parent_of_type(die, 'DW_TAG_base_type')
        if basetype_die is None:
            raise ElfParsingError("Given die does not resolve to a base type")
        return basetype_die
    
    def get_first_parent_of_type(self, die: "elftools_stubs.Die", tags:Union[str, List[str]] ) -> Optional["elftools_stubs.Die"]:
        self.log_debug_process_die(die)
        if isinstance(tags, str):
            tags = [tags]
        prevdie = die
        while True:
            if 'DW_AT_type' not in prevdie.attributes:
                return None
            refaddr = cast(int, prevdie.attributes['DW_AT_type'].value) + prevdie.cu.cu_offset
            nextdie = prevdie.dwarfinfo.get_DIE_from_refaddr(refaddr)
            if nextdie.tag in tags:
                return nextdie
            else:
                prevdie = nextdie

    def get_type_of_var(self, die: "elftools_stubs.Die") -> TypeDescriptor:
        """Go up the hiearchy to find the die that represent the type of the variable. """
        self.log_debug_process_die(die)
        prevdie = die
        enum:Optional["elftools_stubs.Die"] = None
        while True:
            refaddr = prevdie.attributes['DW_AT_type'].value + prevdie.cu.cu_offset
            nextdie = prevdie.dwarfinfo.get_DIE_from_refaddr(refaddr)
            if nextdie.tag =='DW_TAG_structure_type':
                return TypeDescriptor(TypeOfVar.Struct, enum, nextdie)
            elif nextdie.tag == 'DW_TAG_class_type':
                return TypeDescriptor(TypeOfVar.Class, enum, nextdie)
            elif nextdie.tag == 'DW_TAG_array_type':
                return TypeDescriptor(TypeOfVar.Array, enum, nextdie)
            elif nextdie.tag == 'DW_TAG_base_type':
                return TypeDescriptor(TypeOfVar.BaseType, enum, nextdie)
            elif nextdie.tag == 'DW_TAG_pointer_type':
                return TypeDescriptor(TypeOfVar.Pointer, enum, nextdie)
            elif nextdie.tag == 'DW_TAG_union_type':
                return TypeDescriptor(TypeOfVar.Union, enum, nextdie)
            elif nextdie.tag == 'DW_TAG_enumeration_type':
                enum = nextdie  # Will resolve on next iteration (if a type is available)
                if 'DW_AT_type' not in nextdie.attributes: # Clang dwarfv2 may not have type, but has a byte size   
                    if 'DW_AT_byte_size' in nextdie.attributes:
                        return TypeDescriptor(TypeOfVar.EnumOnly, enum, type_die=enum)
                    else:
                        raise ElfParsingError(f"Cannot find the enum underlying type {enum}")

            prevdie = nextdie

    # When we encounter a struct die, we make a definition that we keep global,
    # this definition includes all submember with their respective offset.
    # each time we will encounter a instance of this struct, we will generate a variable for each sub member

    def die_process_struct_class_union(self, die: "elftools_stubs.Die") -> None:
        self.log_debug_process_die(die)

        if die not in self.struct_die_map:
            self.struct_die_map[die] = self.get_composite_type_def(die)


    # Go down the hierarchy to get the whole struct def in a recursive way
    def get_composite_type_def(self, die: "elftools_stubs.Die") -> Struct:
        """Get the definition of a struct/class/union type"""

        self.log_debug_process_die(die)
        if die.tag not in ('DW_TAG_structure_type', 'DW_TAG_class_type', 'DW_TAG_union_type'):
            raise ValueError('DIE must be a structure, class or union type')

        struct = Struct(self.get_name(die))
        is_in_union = die.tag == 'DW_TAG_union_type'
        for child in die.iter_children():
            if child.tag == 'DW_TAG_member':
                member = self.get_member_from_die(child, is_in_union)
                if member is not None:
                    struct.add_member(member)
            elif child.tag == 'DW_TAG_inheritance':
                offset = 0
                if self.has_member_byte_offset(child):
                    offset = self.get_member_byte_offset(child)
                refaddr = child.attributes['DW_AT_type'].value + child.cu.cu_offset
                typedie = child.dwarfinfo.get_DIE_from_refaddr(refaddr)
                if typedie.tag not in ['DW_TAG_structure_type', 'DW_TAG_class_type']:   # Add union here?
                    self.logger.warning(f"Line {get_linenumber()}: Inheritance to a type die {self.make_name_for_log(typedie)}. Not supported yet")
                    continue
                self.die_process_struct_class_union(typedie)
                parent_struct = self.struct_die_map[typedie]
                struct.inherit(parent_struct, offset=offset)

        return struct
    
    def has_member_byte_offset(self, die: "elftools_stubs.Die") -> bool:
        """Tells if an offset relative to the structure base is available on this member die"""
        return 'DW_AT_data_member_location' in die.attributes

    def get_member_byte_offset(self, die: "elftools_stubs.Die") -> int:
        """Tell the offset at which this member is located relative to the structure base"""

        if 'DW_AT_data_member_location' not in die.attributes:
            raise ElfParsingError(f"No member location on die {die}")
        
        val = die.attributes['DW_AT_data_member_location'].value
        if isinstance(val, int):
            return val
        
        if isinstance(val, list):
            if len(val) < 2:
                raise ElfParsingError(f"Invalid member offset data length for die {die}")
            
            if val[0] != self.DW_OP_plus_uconst:
                raise ElfParsingError(f"Does not know how to read member location for die {die}. Operator is unsupported")

            return int.from_bytes(val[1:], byteorder= 'little' if self.endianness == Endianness.Little else 'big') 

        raise ElfParsingError(f"Does not know how to read member location for die {die}")

    def process_enum_only_type(self, enum_die:"elftools_stubs.Die") -> str:
        """With clang Dwarf V2, some enums may have no base type, so we try to deduce it from the propertie son the enum"""
        enum = self.enum_die_map[enum_die]
        if 'DW_AT_byte_size' not in enum_die.attributes:
            raise ElfParsingError(f"Cannot determine enum size {enum_die}")
        bytesize = enum_die.attributes['DW_AT_byte_size'].value
        try:
            encoding = self.DwarfEncoding(cast(int, enum_die.attributes['DW_AT_encoding'].value))
        except:
            encoding = self.DwarfEncoding.DW_ATE_signed if enum.has_signed_value() else self.DwarfEncoding.DW_ATE_unsigned
        basetype = self.get_core_base_type(encoding, bytesize)
        fakename = 'enum_default_'
        fakename += 's' if basetype.is_signed() else 'u'
        fakename += str(basetype.get_size_bit())
        self.varmap.register_base_type(fakename, basetype)
        return fakename
    
    # Read a member die and generate a Struct.Member that we will later on use to register a variable.
    # The struct.Member object contains everything we need to map a
    def get_member_from_die(self, die: "elftools_stubs.Die", is_in_union:bool=False) -> Optional[Struct.Member]:
        self.log_debug_process_die(die)
        try:
            name = self.get_name(die) 
        except Exception:
            name = ""
        type_desc = self.get_type_of_var(die)
        enum:Optional[EmbeddedEnum] = None
        if type_desc.type in (TypeOfVar.Struct, TypeOfVar.Class, TypeOfVar.Union):
            substruct = self.get_composite_type_def(type_desc.type_die)  # recursion
            typename = None
        elif type_desc.type in (TypeOfVar.BaseType, TypeOfVar.EnumOnly):
            if type_desc.enum_die is not None:
                self.die_process_enum(type_desc.enum_die)
                enum = self.enum_die_map[type_desc.enum_die]
        
            if type_desc.type == TypeOfVar.BaseType :
                self.die_process_base_type(type_desc.type_die)    # Just in case it is unknown yet
                typename = self.get_typename_from_die(type_desc.type_die)
            elif type_desc.type == TypeOfVar.EnumOnly:    # clang dwarf v2 may do that for enums
                assert type_desc.enum_die is type_desc.type_die
                typename = self.process_enum_only_type(type_desc.enum_die)
            else:
                raise ElfParsingError("Impossible to process base type")
            
            substruct = None
        else:
            self.logger.warning(f"Line {get_linenumber()}: Found a member with a type die {self.make_name_for_log(type_desc.type_die)} (type={type_desc.type.name}). Not supported yet")
            return None


        # We are looking at a forward declared member.
        if 'DW_AT_declaration' in die.attributes and die.attributes['DW_AT_declaration'].value == True:
            return None
        
        if is_in_union:
            if self.has_member_byte_offset(die) and self.get_member_byte_offset(die) != 0:
                raise ElfParsingError("Encountered an union with a non-zero member location.")
            byte_offset = 0
        else:
            byte_offset = self.get_member_byte_offset(die)

        if 'DW_AT_bit_offset' in die.attributes:
            if 'DW_AT_byte_size' not in die.attributes:
                raise ElfParsingError('Missing DW_AT_byte_size for bitfield %s' % (self.get_name(die, '')))
            if 'DW_AT_bit_size' not in die.attributes:
                raise ElfParsingError('Missing DW_AT_bit_size for bitfield %s' % (self.get_name(die, '')))

        bitsize = die.attributes['DW_AT_bit_size'].value if 'DW_AT_bit_size' in die.attributes else None

        # Not sure about this.
        if 'DW_AT_bit_offset' in die.attributes:
            if self.endianness == Endianness.Little:
                bitoffset = (die.attributes['DW_AT_byte_size'].value * 8) - die.attributes['DW_AT_bit_offset'].value - bitsize
            elif self.endianness == Endianness.Big:
                bitoffset = die.attributes['DW_AT_bit_offset'].value
            else:
                raise ValueError('Unknown endianness')
        else:
            bitoffset = None

        return Struct.Member(
            name=name,
            is_substruct=True if substruct is not None else False,
            original_type_name=typename,
            byte_offset=byte_offset,
            bitoffset=bitoffset,
            bitsize=bitsize,
            substruct=substruct,
            enum=enum,
            is_unnamed = True if (len(name) == 0) else False
        )

    # We have an instance of a struct. Use the location and go down the structure recursively
    # using the members offsets to find the final address that we will apply to the output var
    def register_struct_var(self, die: "elftools_stubs.Die", type_die:"elftools_stubs.Die", location: VariableLocation) -> None:
        """Register an instance of a struct at a given location"""
        path_segments = self.make_varpath(die)
        path_segments.append(self.get_name(die))
        struct = self.struct_die_map[type_die]
        startpoint = Struct.Member(struct.name, is_substruct=True, bitoffset=None, bitsize=None, substruct=struct)

        # Start the recursion that will create all the sub elements
        self.register_member_as_var_recursive(path_segments, startpoint, location, offset=0)

    # Recursive function to dig into a structure and register all possible variables.
    def register_member_as_var_recursive(self, path_segments: List[str], member: Struct.Member, base_location: VariableLocation, offset: int) -> None:
        if member.is_substruct:
            assert member.substruct is not None
            struct = member.substruct
            for name, submember in struct.members.items():
                new_path_segments = path_segments.copy()
                location = base_location.copy()
                if submember.is_substruct:
                    assert submember.byte_offset is not None
                    new_path_segments.append(name)
                    location.add_offset(submember.byte_offset)

                elif submember.byte_offset is not None:
                    offset = submember.byte_offset

                self.register_member_as_var_recursive(new_path_segments, submember, location, offset)
        else:
            location = base_location.copy()
            assert member.byte_offset is not None
            assert member.original_type_name is not None
            location.add_offset(member.byte_offset)

            if self.logger.isEnabledFor(logging.DEBUG):
                fullpath = '/'.join(path_segments + [member.name])
                self.logger.debug(f"Registering {fullpath}")
            self.varmap.add_variable(
                path_segments=path_segments,
                name=member.name,
                original_type_name=member.original_type_name,
                location=location,
                bitoffset=member.bitoffset,
                bitsize=member.bitsize,
                enum = member.enum
            )

    def register_variable(self, 
                          name:str, 
                          path_segments:List[str], 
                          location:VariableLocation, 
                          original_type_name:str, 
                          enum:Optional[EmbeddedEnum] 
                          ) -> None:
        """Adds a variable to the varmap.
        
            :param name: Name of the variable
            :param path_segments: List of str representing each level of display tree
            :param location: The address of the variable
            :param original_type_name: The name of the underlying type. Must be a name coming from the binary. Will resolve to an EmbeddedDataType
            :param enum: Optional enum to associate with the type
        """
        if self.logger.isEnabledFor(logging.DEBUG):
            fullpath = '/'.join(path_segments + [name])
            self.logger.debug(f"Registering {fullpath}")
        self.varmap.add_variable(
            path_segments=path_segments,
            name=name,
            location=location,
            original_type_name=original_type_name,
            enum=enum
        )
    
    def get_location(self, die: "elftools_stubs.Die") -> Optional[VariableLocation]:
        """Try t extract the location from a die. Returns ``None`` if not available"""
        if 'DW_AT_location' in die.attributes:
            dieloc = (die.attributes['DW_AT_location'].value)

            if not isinstance(dieloc, list):
                return None

            if len(dieloc) < 1:
                return None

            if dieloc[0] != self.DW_OP_ADDR:
                return None

            if len(dieloc) < 2:
                self.logger.warning(f'die location is too small: {dieloc}')
                return None

            return VariableLocation.from_bytes(dieloc[1:], self.endianness)
        return None

    def die_process_variable(self, die: "elftools_stubs.Die", location: Optional[VariableLocation] = None) -> None:
        """Process a variable die and insert a variable in the varmap object if it has an absolute address"""
        if location is None:
            location = self.get_location(die)

        if 'DW_AT_specification' in die.attributes:
            vardie = self.get_die_at_spec(die)
            self.die_process_variable(vardie, location) # Recursion
       
        elif 'DW_AT_abstract_origin' in die.attributes:
            vardie = self.get_die_at_abstract_origin(die)
            self.die_process_variable(vardie, location) # Recursion

        else:
            if location is not None:
                type_desc = self.get_type_of_var(die)

                # Composite type
                if type_desc.type in (TypeOfVar.Struct, TypeOfVar.Class, TypeOfVar.Union): 
                    self.die_process_struct_class_union(type_desc.type_die)
                    self.register_struct_var(die, type_desc.type_die, location)
                # Base type
                elif type_desc.type in (TypeOfVar.BaseType, TypeOfVar.EnumOnly):
                    path_segments = self.make_varpath(die)
                    name = self.get_name(die)
                    
                    enum:Optional[EmbeddedEnum] = None
                    if type_desc.enum_die is not None:
                        self.die_process_enum(type_desc.enum_die)
                        enum = self.enum_die_map[type_desc.enum_die]

                    if type_desc.type == TypeOfVar.BaseType :   # Most common case
                        self.die_process_base_type(type_desc.type_die)    # Just in case it is unknown yet
                        typename = self.get_typename_from_die(type_desc.type_die)
                    elif type_desc.type == TypeOfVar.EnumOnly:    # clang dwarf v2 may do that for enums
                        assert type_desc.enum_die is type_desc.type_die
                        assert type_desc.enum_die is not None
                        typename = self.process_enum_only_type(type_desc.enum_die)
                    else:
                        raise ElfParsingError("Impossible to process base type")

                    self.register_variable(
                        name=name,
                        path_segments=path_segments,
                        location=location,
                        original_type_name=typename,
                        enum=enum
                    )
                else:
                    self.logger.warning(f"Line {get_linenumber()}: Found a variable with a type die {self.make_name_for_log(type_desc.type_die)} (type={type_desc.type.name}). Not supported yet")

    def get_varpath_from_hierarchy(self, die: "elftools_stubs.Die") -> List[str]:
        """Go up in the DWARF hierarchy and make a path segment for each level"""
        segments: List[str] = []
        parent = die.get_parent()
        while parent is not None:
            if parent.tag == 'DW_TAG_compile_unit':
                break

            try:
                if self.has_linkage_name(parent):
                    name = self.get_linkage_name(parent)
                else:
                    name = self.get_name(parent)
            except Exception:
                if 'DW_AT_specification' in parent.attributes:
                    parent2 = self.get_die_at_spec(parent)
                    name = self.get_name(parent2)

            if name is not None:
                segments.insert(0, name)
            parent = parent.get_parent()
        return segments

    def get_varpath_from_linkage_name(self, die: "elftools_stubs.Die") -> List[str]:
        """Generate path segments by parsing the linkage name. Relies on the ability to demangle"""
        demangled = self.get_linkage_name(die)
        segments = demangled.split('::')
        try:
            name = self.get_name(die)
            if segments[-1] == name:
                segments.pop()
        except Exception:
            pass
        return segments

    def make_varpath(self, die: "elftools_stubs.Die") -> List[str]:
        """Generate the display path for a die, either from the hierarchy or the linkage name"""
        if self.has_linkage_name(die):
            segments = self.get_varpath_from_linkage_name(die)
        else:
            segments = self.get_varpath_from_hierarchy(die)

        if self.is_external(die):
            segments.insert(0, self.GLOBAL)
        else:
            segments.insert(0, self.STATIC)
            segments.insert(1, self.get_cu_name(die))

        return segments
