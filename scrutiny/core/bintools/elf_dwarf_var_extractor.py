#    elf_dwarf_var_extractor.py
#        Reads a .elf file, extract the DWARF debugging symbols and make a VarMap object out
#        of it.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

__all__ = ['ElfDwarfVarExtractor']

from elftools.dwarf.die import DIE
from elftools.dwarf.compileunit import CompileUnit
from elftools.dwarf.dwarfinfo import DWARFInfo
from elftools.elf.elffile import ELFFile

import os
from enum import Enum, auto
import logging
import inspect
from dataclasses import dataclass
from inspect import currentframe

from scrutiny.core.bintools.demangler import GccDemangler
from scrutiny.core.varmap import VarMap
from scrutiny.core.basic_types import *
from scrutiny.core.variable import *
from scrutiny.core.embedded_enum import *
from scrutiny.exceptions import EnvionmentNotSetUpException
from scrutiny import tools
from scrutiny.core.logging import DUMPDATA_LOGLEVEL

from scrutiny.tools.typing import *

class Attrs:
    DW_AT_declaration = 'DW_AT_declaration'
    DW_AT_comp_dir = 'DW_AT_comp_dir'
    DW_AT_specification = 'DW_AT_specification'
    DW_AT_abstract_origin = 'DW_AT_abstract_origin'
    DW_AT_name = 'DW_AT_name'
    DW_AT_linkage_name = 'DW_AT_linkage_name'
    DW_AT_MIPS_linkage_name = 'DW_AT_MIPS_linkage_name'
    DW_AT_external = 'DW_AT_external'
    DW_AT_byte_size = 'DW_AT_byte_size'
    DW_AT_encoding = 'DW_AT_encoding'
    DW_AT_const_value = 'DW_AT_const_value'
    DW_AT_type = 'DW_AT_type'
    DW_AT_data_member_location = 'DW_AT_data_member_location'
    DW_AT_bit_offset = 'DW_AT_bit_offset'
    DW_AT_bit_size = 'DW_AT_bit_size'
    DW_AT_data_bit_offset = 'DW_AT_data_bit_offset'
    DW_AT_location = 'DW_AT_location'
    DW_AT_MIPS_fde = 'DW_AT_MIPS_fde'
    DW_AT_producer = 'DW_AT_producer'

class Tags:
    DW_TAG_structure_type = 'DW_TAG_structure_type'
    DW_TAG_enumeration_type = 'DW_TAG_enumeration_type'
    DW_TAG_union_type = 'DW_TAG_union_type'
    DW_TAG_compile_unit = 'DW_TAG_compile_unit'
    DW_TAG_variable = 'DW_TAG_variable'
    DW_TAG_enumerator = 'DW_TAG_enumerator'
    DW_TAG_base_type = 'DW_TAG_base_type'
    DW_TAG_class_type = 'DW_TAG_class_type'
    DW_TAG_array_type = 'DW_TAG_array_type'
    DW_TAG_pointer_type = 'DW_TAG_pointer_type'
    DW_TAG_member = 'DW_TAG_member'
    DW_TAG_inheritance = 'DW_TAG_inheritance'

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

class TypeOfVar(Enum):
    BaseType = auto()
    Struct = auto()
    Class = auto()
    Union = auto()
    Pointer = auto()
    Array = auto()
    EnumOnly = auto()  # Clang dwarf v2


@dataclass
class TypeDescriptor:
    type: TypeOfVar
    enum_die: Optional[DIE]
    type_die: DIE

class Architecture(Enum):
    UNKNOWN=auto()
    TI_C28x = auto()

class Compiler(Enum):
    UNKNOWN=auto()
    TI_C28_CGT=auto()
    CLANG=auto()
    GCC=auto()

def get_linenumber() -> int:
    """Return the line number of the caller"""
    cf = currentframe()
    if cf is None:
        return -1
    if cf.f_back is None:
        return -1
    if cf.f_back.f_lineno is None:
        return -1

    return int(cf.f_back.f_lineno)

class ElfParsingError(Exception):
    pass


class CuName:
    """
    Handles a compile unit name. Useful to build a unique name as small as possible.
    """
    _class_internal_id = 0
    PATH_JOIN_CHAR = '_'

    cu: CompileUnit
    fullpath: str
    filename: str
    display_name: str
    segments: List[str]

    def __init__(self, cu: CompileUnit, fullpath: str) -> None:
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


@dataclass
class Context:
    arch:Architecture
    endianess:Endianness
    cu_compiler:Compiler

class ElfDwarfVarExtractor:
    DEFAULTS_NAMES:Dict[str,str] = {
        Tags.DW_TAG_structure_type: '<struct>',
        Tags.DW_TAG_enumeration_type: '<enum>',
        Tags.DW_TAG_union_type: '<union>'
    }

    STATIC = 'static'
    GLOBAL = 'global'
    MAX_CU_DISPLAY_NAME_LENGTH = 40
    DW_OP_ADDR = 3
    DW_OP_plus_uconst = 0x23

    varmap: VarMap
    die2typeid_map: Dict[DIE, str]
    die2vartype_map: Dict[DIE, EmbeddedDataType]
    cu_name_map: Dict[CompileUnit, str]
    enum_die_map: Dict[DIE, EmbeddedEnum]
    struct_die_map: Dict[DIE, Struct]
    cppfilt: Optional[str]
    logger: logging.Logger

    _context:Context

    def __init__(self, filename: Optional[str] = None, 
                 cppfilt: Optional[str] = None
                 ) -> None:
        self.varmap = VarMap()    # This is what we want to generate.
        self.die2typeid_map = {}
        self.die2vartype_map = {}
        self.cu_name_map = {}   # maps a CompileUnit object to it's unique display name
        self.enum_die_map = {}
        self.struct_die_map = {}
        self.cppfilt = cppfilt
        self.logger = logging.getLogger(self.__class__.__name__)
        self._context = Context(    # Default
            arch=Architecture.UNKNOWN,
            endianess=Endianness.Little,
            cu_compiler=Compiler.UNKNOWN
        )

        self.initial_stack_depth = len(inspect.stack())

        if filename is not None:
            self._load_from_elf_file(filename)


    def _make_name_for_log(self, die: Optional[DIE]) -> str:
        if die is None:
            return "<None>"
        name = self.get_name(die, default='', nolog=True)

        return f'{die.tag} <{die.offset:x}> "{name}"'

    def _log_debug_process_die(self, die: DIE) -> None:
        if self.logger.isEnabledFor(DUMPDATA_LOGLEVEL):  # pragma: no cover
            stack_depth = len(inspect.stack()) - self.initial_stack_depth - 1
            stack_depth = max(stack_depth, 1)
            funcname = inspect.stack()[1][3]
            pad = '|  ' * (stack_depth - 1) + '|--'
            self.logger.debug(f"{pad}{funcname}({self._make_name_for_log(die)})")

    def get_varmap(self) -> VarMap:
        return self.varmap

    def make_cu_name_map(self, dwarfinfo: DWARFInfo) -> None:
        """ Builds a dictionary that maps a CompileUnit object to a unique displayable name """

        fullpath_cu_tuple_list = []
        cu: CompileUnit
        for cu in dwarfinfo.iter_CUs():
            topdie: DIE = cu.get_top_DIE()
            if topdie.tag != Tags.DW_TAG_compile_unit:
                raise ElfParsingError('Top die should be a compile unit')

            comp_dir = None
            name = self.get_name_no_none(topdie, 'unnamed_cu')
            if Attrs.DW_AT_comp_dir in topdie.attributes:
                comp_dir = topdie.attributes[Attrs.DW_AT_comp_dir].value.decode('utf8')
                fullpath = os.path.join(comp_dir, name)
            else:
                fullpath = os.path.abspath(name)

            fullpath_cu_tuple_list.append((fullpath, cu))

        displayname_cu_tuple_list = self.make_unique_display_name(fullpath_cu_tuple_list)

        for item in displayname_cu_tuple_list:
            self.cu_name_map[item[1]] = item[0]

    @classmethod
    def make_unique_display_name(cls, fullpath_cu_tuple_list: List[Tuple[str, CompileUnit]]) -> List[Tuple[str, CompileUnit]]:
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

        displayname_cu_tuple_list: List[Tuple[str, CompileUnit]] = []
        for displayname in displayname_map:
            displayname_cu_tuple_list.append((displayname, displayname_map[displayname][0].cu))
        return displayname_cu_tuple_list

    def get_cu_name(self, die: DIE) -> str:
        return self.cu_name_map[die.cu]

    def get_die_at_spec(self, die: DIE) -> DIE:
        self._log_debug_process_die(die)
        return die.get_DIE_from_attribute(Attrs.DW_AT_specification)

    def get_die_at_abstract_origin(self, die: DIE) -> DIE:
        self._log_debug_process_die(die)
        return die.get_DIE_from_attribute(Attrs.DW_AT_abstract_origin)

    def get_name(self, die: DIE, default: Optional[str] = None, nolog: bool = False, raise_if_none:bool = False) -> Optional[str]:
        if not nolog:
            self._log_debug_process_die(die)
        if Attrs.DW_AT_name in die.attributes:
            return cast(str, die.attributes[Attrs.DW_AT_name].value.decode('ascii'))

        if default is not None:
            return default
        
        if die.tag in self.DEFAULTS_NAMES:
            return self.DEFAULTS_NAMES[die.tag]
        
        if raise_if_none:
            raise ElfParsingError(f"No name available on die {die}")
        return None
    
    def get_name_no_none(self,  die: DIE, default: Optional[str] = None, nolog: bool = False) -> str:
        name = self.get_name(die, default, nolog, raise_if_none=True)
        assert name is not None
        return name
    
    def has_linkage_name(self, die:DIE) -> bool:
        return self.get_mangled_linkage_name(die) is not None
    
    def get_mangled_linkage_name(self, die:DIE) -> Optional[str]:
        mangled_encoded:Optional[str] = None

        if Attrs.DW_AT_linkage_name in die.attributes:
            mangled_encoded = die.attributes[Attrs.DW_AT_linkage_name].value

        if self._context.cu_compiler == Compiler.TI_C28_CGT:
            if Attrs.DW_AT_MIPS_fde in die.attributes:
                mangled_encoded = die.attributes[Attrs.DW_AT_MIPS_fde].value
        else:
            if Attrs.DW_AT_MIPS_linkage_name in die.attributes:
                mangled_encoded = die.attributes[Attrs.DW_AT_MIPS_linkage_name].value
        
        if isinstance(mangled_encoded, bytes):
            return mangled_encoded.decode('ascii')
        
        if isinstance(mangled_encoded, str):
            return mangled_encoded
        
        return None
    
    def get_demangled_linkage_name(self, die: DIE) -> Optional[str]:
        self._log_debug_process_die(die)
        mangled_name = self.get_mangled_linkage_name(die)
        if mangled_name is None:
            return None

        return self.demangler.demangle(mangled_name)

    def is_external(self, die: DIE) -> bool:
        """Tells if the die is accessible from outside the compile unit. If it is, it's global, otherwise it's static."""
        try:
            return bool(die.attributes[Attrs.DW_AT_external].value)
        except Exception:
            return False

    def get_core_base_type(self, encoding: DwarfEncoding, bytesize: int) -> EmbeddedDataType:

        encoding_map: Dict[DwarfEncoding, Dict[int, EmbeddedDataType]] = {
            DwarfEncoding.DW_ATE_address: {
                # todo
            },
            DwarfEncoding.DW_ATE_boolean: {
                1: EmbeddedDataType.boolean,
                2: EmbeddedDataType.uint16,
                4: EmbeddedDataType.uint32,
                8: EmbeddedDataType.uint64
            },
            DwarfEncoding.DW_ATE_complex_float: {
                1: EmbeddedDataType.cfloat8,
                2: EmbeddedDataType.cfloat16,
                4: EmbeddedDataType.cfloat32,
                8: EmbeddedDataType.cfloat64,
                16: EmbeddedDataType.cfloat128,
                32: EmbeddedDataType.cfloat256
            },
            DwarfEncoding.DW_ATE_float: {
                1: EmbeddedDataType.float8,
                2: EmbeddedDataType.float16,
                4: EmbeddedDataType.float32,
                8: EmbeddedDataType.float64,
                16: EmbeddedDataType.float128,
                32: EmbeddedDataType.float256

            },
            DwarfEncoding.DW_ATE_signed: {
                1: EmbeddedDataType.sint8,
                2: EmbeddedDataType.sint16,
                4: EmbeddedDataType.sint32,
                8: EmbeddedDataType.sint64,
                16: EmbeddedDataType.sint128,
                32: EmbeddedDataType.sint256
            },
            DwarfEncoding.DW_ATE_signed_char: {
                1: EmbeddedDataType.sint8,
                2: EmbeddedDataType.sint16,
                4: EmbeddedDataType.sint32,
                8: EmbeddedDataType.sint64,
                16: EmbeddedDataType.sint128,
                32: EmbeddedDataType.sint256
            },
            DwarfEncoding.DW_ATE_unsigned: {
                1: EmbeddedDataType.uint8,
                2: EmbeddedDataType.uint16,
                4: EmbeddedDataType.uint32,
                8: EmbeddedDataType.uint64,
                16: EmbeddedDataType.uint128,
                32: EmbeddedDataType.uint256
            },
            DwarfEncoding.DW_ATE_unsigned_char: {
                1: EmbeddedDataType.uint8,
                2: EmbeddedDataType.uint16,
                4: EmbeddedDataType.uint32,
                8: EmbeddedDataType.uint64,
                16: EmbeddedDataType.uint128,
                32: EmbeddedDataType.uint256
            },
            DwarfEncoding.DW_ATE_UTF: {
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

    def _load_from_elf_file(self, filename: str) -> None:
        with open(filename, 'rb') as f:
            elffile = ELFFile(f)

            if not elffile.has_dwarf_info():
                raise ElfParsingError('File has no DWARF info')

            self.dwarfinfo = elffile.get_dwarf_info()

            self._context.arch = self._identify_arch()  
            self._context.endianess = self._identify_endianness(self._context.arch)
            self.varmap.set_endianness(self._context.endianess)

            self.make_cu_name_map(self.dwarfinfo)
            self.demangler = GccDemangler(self.cppfilt)  # todo : adapt according to compile unit producer

            if not self.demangler.can_run():
                raise EnvionmentNotSetUpException("Demangler cannot be used. %s" % self.demangler.get_error())

            self.initial_stack_depth = len(inspect.stack()) 

            bad_support_warning_written = False
            for cu in self.dwarfinfo.iter_CUs():
                self._context.cu_compiler = self._identify_compiler(cu)
                if cu.header['version'] not in (2, 3, 4):
                    if not bad_support_warning_written:
                        bad_support_warning_written = True
                        self.logger.warning(f"DWARF format version {cu.header['version']} is not well supported, output may be incomplete")
                die = cu.get_top_DIE()
                self.extract_var_recursive(die)  # Recursion start point

    def _identify_arch(self) -> Architecture:
        machine_arch = self.dwarfinfo.config.machine_arch.lower().strip()
        if 'c2000' in machine_arch and 'ti' in machine_arch:
            return Architecture.TI_C28x

        return Architecture.UNKNOWN
    
    def _identify_compiler(self, cu:CompileUnit) -> Compiler:
        cu_die = cu.get_top_DIE()
        if cu_die.tag != Tags.DW_TAG_compile_unit:
            return Compiler.UNKNOWN
        
        if Attrs.DW_AT_producer in cu_die.attributes:
            producer = str(cu_die.attributes[Attrs.DW_AT_producer].value).strip().lower()
            if 'ti' in producer and 'c2000' in producer:
                return Compiler.TI_C28_CGT
            if 'clang' in producer:
                return Compiler.CLANG
            if 'gnu' in producer:
                return Compiler.GCC
            
        return Compiler.UNKNOWN
    

    def _identify_endianness(self, arch:Architecture) -> Endianness:
        # No easy way to know it. DW_AT_endianity is introduced in dwarf v4, but only applied on data block and not used by compilers...
        # We make the assumption that the endianness is the same at the binary level
        
        if arch == Architecture.TI_C28x:
            return Endianness.Big

        return Endianness.Little    #  Little is the most common, default on this


    def extract_var_recursive(self, die: DIE) -> None:
        # Finds all "variable" tags and create an entry in the varmap.
        # Types / structures / enums are discovered as we go. We only take
        # definitions that are used by a variables, the rest will be ignored.

        self._log_debug_process_die(die)

        if die.tag == Tags.DW_TAG_variable:
            self.die_process_variable(die)

        for child in die.iter_children():
            try:
                self.extract_var_recursive(child)
            except Exception as e:
                tools.log_exception(self.logger, e, f"Failed to extract var under {child}.")

    def get_typename_from_die(self, die: DIE) -> str:
        return cast(bytes, die.attributes[Attrs.DW_AT_name].value).decode('ascii')

    def get_size_from_type_die(self, die:DIE) -> int:
        if Attrs.DW_AT_byte_size not in die.attributes:
            raise ElfParsingError(f'Missing DW_AT_byte_size on type die {die}')
        val = cast(int, die.attributes[Attrs.DW_AT_byte_size].value)
        if self._context.arch == Architecture.TI_C28x:
            return val*2    # char = 16 bits
        
        return val

    # Process die of type "base type". Register the type in the global index and maps it to a known type.
    def die_process_base_type(self, die: DIE) -> None:
        self._log_debug_process_die(die)
        name = self.get_typename_from_die(die)
        encoding = DwarfEncoding(cast(int, die.attributes[Attrs.DW_AT_encoding].value))
        bytesize = self.get_size_from_type_die(die)
        basetype = self.get_core_base_type(encoding, bytesize)
        self.logger.debug(f"Registering base type: {name} as {basetype.name}")
        self.varmap.register_base_type(name, basetype)

        self.die2typeid_map[die] = self.varmap.get_type_id(name)
        self.die2vartype_map[die] = basetype
    

    def die_process_enum(self, die: DIE) -> None:
        self._log_debug_process_die(die)
        name = self.get_name(die)
        
        if self._context.cu_compiler == Compiler.TI_C28_CGT:
            # cl2000 embeds the full mangled path in the DW_AT_NAME attribute, 
            # ex : _ZN13FileNamespace14File3TestClass16File3EnumInClassE = FileNamespace::File3TestClass::File3EnumInClass
            demangled_name = self.demangler.demangle(name)
            name = demangled_name.split('::')[-1]

        if die not in self.enum_die_map and name is not None:
            enum = EmbeddedEnum(name)

            for child in die.iter_children():
                if child.tag != Tags.DW_TAG_enumerator:
                    continue

                name = self.get_name_no_none(child)
                if self._context.cu_compiler == Compiler.TI_C28_CGT:
                    # cl2000 embeds the full mangled path in the DW_AT_NAME attribute, 
                    # ex :_ZN13FileNamespace14File3TestClass3BBBE = FileNamespace::File3TestClass::BBB
                    demangled_name = self.demangler.demangle(name)
                    name = demangled_name.split('::')[-1]

                if Attrs.DW_AT_const_value in child.attributes:
                    value = cast(int, child.attributes[Attrs.DW_AT_const_value].value)
                    enum.add_value(name=name, value=value)
                else:
                    self.logger.error('Enumerator without value')

            self.enum_die_map[die] = enum

    def get_type_of_var(self, die: DIE) -> TypeDescriptor:
        """Go up the hiearchy to find the die that represent the type of the variable. """
        self._log_debug_process_die(die)
        prevdie = die
        enum: Optional[DIE] = None
        while True:
            nextdie = prevdie.get_DIE_from_attribute(Attrs.DW_AT_type)
            if nextdie.tag == Tags.DW_TAG_structure_type:
                return TypeDescriptor(TypeOfVar.Struct, enum, nextdie)
            elif nextdie.tag == Tags.DW_TAG_class_type:
                return TypeDescriptor(TypeOfVar.Class, enum, nextdie)
            elif nextdie.tag == Tags.DW_TAG_array_type:
                return TypeDescriptor(TypeOfVar.Array, enum, nextdie)
            elif nextdie.tag == Tags.DW_TAG_base_type:
                return TypeDescriptor(TypeOfVar.BaseType, enum, nextdie)
            elif nextdie.tag == Tags.DW_TAG_pointer_type:
                return TypeDescriptor(TypeOfVar.Pointer, enum, nextdie)
            elif nextdie.tag == Tags.DW_TAG_union_type:
                return TypeDescriptor(TypeOfVar.Union, enum, nextdie)
            elif nextdie.tag == Tags.DW_TAG_enumeration_type:
                enum = nextdie  # Will resolve on next iteration (if a type is available)
                if Attrs.DW_AT_type not in nextdie.attributes:  # Clang dwarfv2 may not have type, but has a byte size
                    if Attrs.DW_AT_byte_size in nextdie.attributes:
                        return TypeDescriptor(TypeOfVar.EnumOnly, enum, type_die=enum)
                    else:
                        raise ElfParsingError(f"Cannot find the enum underlying type {enum}")

            prevdie = nextdie

    # When we encounter a struct die, we make a definition that we keep global,
    # this definition includes all submember with their respective offset.
    # each time we will encounter a instance of this struct, we will generate a variable for each sub member

    def die_process_struct_class_union(self, die: DIE) -> None:
        self._log_debug_process_die(die)

        if die not in self.struct_die_map:
            self.struct_die_map[die] = self.get_composite_type_def(die)

    # Go down the hierarchy to get the whole struct def in a recursive way

    def get_composite_type_def(self, die: DIE) -> Struct:
        """Get the definition of a struct/class/union type"""

        self._log_debug_process_die(die)
        if die.tag not in (Tags.DW_TAG_structure_type, Tags.DW_TAG_class_type, Tags.DW_TAG_union_type):
            raise ValueError('DIE must be a structure, class or union type')

        struct = Struct(self.get_name_no_none(die))
        is_in_union = die.tag == Tags.DW_TAG_union_type
        for child in die.iter_children():
            if child.tag == Tags.DW_TAG_member:
                member = self.get_member_from_die(child, is_in_union)
                if member is not None:
                    struct.add_member(member)
            elif child.tag == Tags.DW_TAG_inheritance:
                offset = 0
                if self.has_member_byte_offset(child):
                    offset = self.get_member_byte_offset(child)
                typedie = child.get_DIE_from_attribute(Attrs.DW_AT_type)
                if typedie.tag not in [Tags.DW_TAG_structure_type, Tags.DW_TAG_class_type]:   # Add union here?
                    self.logger.warning(f"Line {get_linenumber()}: Inheritance to a type die {self._make_name_for_log(typedie)}. Not supported yet")
                    continue
                self.die_process_struct_class_union(typedie)
                parent_struct = self.struct_die_map[typedie]
                struct.inherit(parent_struct, offset=offset)

        return struct

    def has_member_byte_offset(self, die: DIE) -> bool:
        """Tells if an offset relative to the structure base is available on this member die"""
        return Attrs.DW_AT_data_member_location in die.attributes

    def get_member_byte_offset(self, die: DIE) -> int:
        """Tell the offset at which this member is located relative to the structure base"""
        if Attrs.DW_AT_data_member_location not in die.attributes:
            # DWARF V4. 5.5.6: If the beginning of the data member is the same as the beginning of the containing entity then neither attribute is required.
            return 0

        val = die.attributes[Attrs.DW_AT_data_member_location].value
        if isinstance(val, int):
            return val

        if isinstance(val, list):
            if len(val) < 2:
                raise ElfParsingError(f"Invalid member offset data length for die {die}")

            if val[0] != self.DW_OP_plus_uconst:
                raise ElfParsingError(f"Does not know how to read member location for die {die}. Operator is unsupported")

            return int.from_bytes(val[1:], byteorder='little' if self._context.endianess == Endianness.Little else 'big')

        raise ElfParsingError(f"Does not know how to read member location for die {die}")

    def process_enum_only_type(self, enum_die: DIE) -> str:
        """With clang Dwarf V2, some enums may have no base type, so we try to deduce it from the properties on the enum"""
        enum = self.enum_die_map[enum_die]
        if Attrs.DW_AT_byte_size not in enum_die.attributes:
            raise ElfParsingError(f"Cannot determine enum size {enum_die}")
        bytesize = enum_die.attributes[Attrs.DW_AT_byte_size].value
        try:
            encoding = DwarfEncoding(cast(int, enum_die.attributes[Attrs.DW_AT_encoding].value))
        except:
            encoding = DwarfEncoding.DW_ATE_signed if enum.has_signed_value() else DwarfEncoding.DW_ATE_unsigned
        basetype = self.get_core_base_type(encoding, bytesize)
        fakename = 'enum_default_'
        fakename += 's' if basetype.is_signed() else 'u'
        fakename += str(basetype.get_size_bit())
        self.varmap.register_base_type(fakename, basetype)
        return fakename

    # Read a member die and generate a Struct.Member that we will later on use to register a variable.
    # The struct.Member object contains everything we need to map a
    def get_member_from_die(self, die: DIE, is_in_union: bool = False) -> Optional[Struct.Member]:
        self._log_debug_process_die(die)

        name = self.get_name(die)
        if name is None:
            name = ''

        type_desc = self.get_type_of_var(die)
        enum: Optional[EmbeddedEnum] = None
        if type_desc.type in (TypeOfVar.Struct, TypeOfVar.Class, TypeOfVar.Union):
            substruct = self.get_composite_type_def(type_desc.type_die)  # recursion
            typename = None
        elif type_desc.type in (TypeOfVar.BaseType, TypeOfVar.EnumOnly):
            if type_desc.enum_die is not None:
                self.die_process_enum(type_desc.enum_die)
                enum = self.enum_die_map[type_desc.enum_die]

            if type_desc.type == TypeOfVar.BaseType:
                self.die_process_base_type(type_desc.type_die)    # Just in case it is unknown yet
                typename = self.get_typename_from_die(type_desc.type_die)
            elif type_desc.type == TypeOfVar.EnumOnly:    # clang dwarf v2 may do that for enums
                assert type_desc.enum_die is type_desc.type_die
                typename = self.process_enum_only_type(type_desc.enum_die)
            else:
                raise ElfParsingError("Impossible to process base type")

            substruct = None
        else:
            self.logger.warning(
                f"Line {get_linenumber()}: Found a member with a type die {self._make_name_for_log(type_desc.type_die)} (type={type_desc.type.name}). Not supported yet")
            return None

        # We are looking at a forward declared member.
        if Attrs.DW_AT_declaration in die.attributes and die.attributes[Attrs.DW_AT_declaration].value == True:
            return None

        if is_in_union:
            if self.has_member_byte_offset(die) and self.get_member_byte_offset(die) != 0:
                raise ElfParsingError("Encountered an union with a non-zero member location.")
            byte_offset = 0
        else:
            byte_offset = self.get_member_byte_offset(die)

        is_bitfield = Attrs.DW_AT_bit_offset in die.attributes or Attrs.DW_AT_bit_size in die.attributes
        
        bitoffset:Optional[int] = None
        bitsize:Optional[int] = None

        if is_bitfield:
            bytesize:Optional[int] = None

            if Attrs.DW_AT_byte_size in die.attributes:
                bytesize = int(die.attributes[Attrs.DW_AT_byte_size].value)
            elif type_desc.type in [TypeOfVar.BaseType, TypeOfVar.EnumOnly]:
                bytesize = self.get_size_from_type_die(type_desc.type_die)
            else:
                raise ElfParsingError(f'Cannot get byte size for bitfield {self.get_name(die, '')}' )
            
            if Attrs.DW_AT_bit_size not in die.attributes:
                raise ElfParsingError(f'Missing {Attrs.DW_AT_bit_size} for bitfield {self.get_name(die, '')}')

            bitsize = die.attributes[Attrs.DW_AT_bit_size].value

            if Attrs.DW_AT_bit_offset in die.attributes:
                bitoffset = int(die.attributes[Attrs.DW_AT_bit_offset].value)
            elif Attrs.DW_AT_data_bit_offset in die.attributes:
                bitoffset = int(die.attributes[Attrs.DW_AT_data_bit_offset].value)
            else:
                bitoffset = 0   # Dwarf V4 allow this. 

            if self._context.endianess == Endianness.Little:
                bitoffset = (bytesize * 8) - bitoffset - bitsize

        return Struct.Member(
            name=name,
            is_substruct=True if substruct is not None else False,
            original_type_name=typename,
            byte_offset=byte_offset,
            bitoffset=bitoffset,
            bitsize=bitsize,
            substruct=substruct,
            enum=enum,
            is_unnamed=True if (len(name) == 0) else False
        )

    # We have an instance of a struct. Use the location and go down the structure recursively
    # using the members offsets to find the final address that we will apply to the output var
    def register_struct_var(self, die: DIE, type_die: DIE, location: VariableLocation) -> None:
        """Register an instance of a struct at a given location"""
        path_segments = self.make_varpath(die)
        #path_segments.append(self.get_name_no_none(die))
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

            if self.logger.isEnabledFor(logging.DEBUG):  # pragma: no cover
                fullpath = '/'.join(path_segments + [member.name])
                self.logger.debug(f"Registering {fullpath}")
            self.varmap.add_variable(
                path_segments=path_segments,
                name=member.name,
                original_type_name=member.original_type_name,
                location=location,
                bitoffset=member.bitoffset,
                bitsize=member.bitsize,
                enum=member.enum
            )

    def register_variable(self,
                          name: str,
                          path_segments: List[str],
                          location: VariableLocation,
                          original_type_name: str,
                          enum: Optional[EmbeddedEnum]
                          ) -> None:
        """Adds a variable to the varmap.

            :param name: Name of the variable
            :param path_segments: List of str representing each level of display tree
            :param location: The address of the variable
            :param original_type_name: The name of the underlying type. Must be a name coming from the binary. Will resolve to an EmbeddedDataType
            :param enum: Optional enum to associate with the type
        """
        if self.logger.isEnabledFor(logging.DEBUG):  # pragma: no cover
            fullpath = '/'.join(path_segments + [name])
            self.logger.debug(f"Registering {fullpath}")
        self.varmap.add_variable(
            path_segments=path_segments,
            name=name,
            location=location,
            original_type_name=original_type_name,
            enum=enum
        )

    def get_location(self, die: DIE) -> Optional[VariableLocation]:
        """Try t extract the location from a die. Returns ``None`` if not available"""
        if Attrs.DW_AT_location in die.attributes:
            dieloc = (die.attributes[Attrs.DW_AT_location].value)

            if not isinstance(dieloc, list):
                return None

            if len(dieloc) < 1:
                return None

            if dieloc[0] != self.DW_OP_ADDR:
                return None

            if len(dieloc) < 2:
                self.logger.warning(f'die location is too small: {dieloc}')
                return None

            return VariableLocation.from_bytes(dieloc[1:], self._context.endianess)
        return None

    def die_process_variable(self, die: DIE, location: Optional[VariableLocation] = None) -> None:
        """Process a variable die and insert a variable in the varmap object if it has an absolute address"""
        if location is None:
            location = self.get_location(die)

        if Attrs.DW_AT_specification in die.attributes:
            vardie = self.get_die_at_spec(die)
            self.die_process_variable(vardie, location=location)  # Recursion

        elif Attrs.DW_AT_abstract_origin in die.attributes:
            vardie = self.get_die_at_abstract_origin(die)
            self.die_process_variable(vardie, location=location)  # Recursion

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
                    name = path_segments.pop()
                    #name = self.get_name_no_none(die)

                    enum: Optional[EmbeddedEnum] = None
                    if type_desc.enum_die is not None:
                        self.die_process_enum(type_desc.enum_die)
                        enum = self.enum_die_map[type_desc.enum_die]

                    if type_desc.type == TypeOfVar.BaseType:   # Most common case
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
                    self.logger.warning(
                        f"Line {get_linenumber()}: Found a variable with a type die {self._make_name_for_log(type_desc.type_die)} (type={type_desc.type.name}). Not supported yet")

    def make_varpath_recursive(self, die:DIE, segments:List[str]) -> List[str]:
        if die.tag == Tags.DW_TAG_compile_unit:
            return segments
        
        name = self.get_demangled_linkage_name(die)
        if name is not None:
            parts = name.split('::')
            return parts + segments

        name = self.get_name(die)
        if name is None:
            if Attrs.DW_AT_specification in die.attributes:
                spec_die = self.get_die_at_spec(die)
                name = self.get_name(spec_die) 
        
        if name is not None:
            segments.insert(0, name)
            parent = die.get_parent()
            if parent is not None:
                return self.make_varpath_recursive(parent, segments=segments)

        return segments


    def make_varpath(self, die: DIE) -> List[str]:
        """Generate the display path for a die, either from the hierarchy or the linkage name"""
        segments = self.make_varpath_recursive(die, []) # Stops at the compile unit (without including it)

        if self.is_external(die):
            segments.insert(0, self.GLOBAL)
        else:
            segments.insert(0, self.STATIC)
            segments.insert(1, self.get_cu_name(die))

        return segments
