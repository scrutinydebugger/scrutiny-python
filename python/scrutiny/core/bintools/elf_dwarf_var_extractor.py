#    elf_dwarf_var_extractor.py
#        Reads a .elf file, extract the DWARF debugging symbols and make a VarMap object out
#        of it.
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

from elftools.elf.elffile import ELFFile    # type: ignore
import os
import sys
from enum import Enum
from .demangler import GccDemangler
import logging
import re
import json

from scrutiny.core import *


class CuName:
    """
    Handles a compile unit name. Useful to build a unique name as small as possible.
    """
    _class_internal_id = 0
    PATH_JOIN_CHAR = '_'

    def __init__(self, cu, fullpath):
        self.cu = cu
        self.fullpath = os.path.normpath(fullpath)
        self.filename = os.path.basename(fullpath)
        self.display_name = self.filename
        self.segments = os.path.split(self.fullpath)[0].split(os.sep)

    def get_display_name(self):
        return self.display_name.replace('/', '-')

    def get_fullpath(self):
        return self.fullpath

    def go_up(self):
        if len(self.segments) > 0:
            last_dir = self.segments.pop()
            if last_dir == '':
                raise Exception('Cannot go up')
            self.display_name = self.PATH_JOIN_CHAR.join([last_dir, self.display_name])
        else:
            raise Exception('Cannot go up')

    def make_unique_numbered_name(self, name_set):
        i = 0
        while True:
            candidate = 'cu%d_%s' % (i, self.filename)
            if candidate not in name_set:
                return candidate
            i += 1


class ElfDwarfVarExtractor:
    defaults_names = {
        'DW_TAG_structure_type': '<struct>',
        'DW_TAG_enumeration_type': '<enum>'
    }

    STATIC = 'static'
    GLOBAL = 'global'
    MAX_CU_DISPLAY_NAME_LENGTH = 40
    DW_OP_ADDR = 3

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

    def __init__(self, filename=None):
        self.varmap = VarMap()    # This is what we want to generate.
        self.die2typeid_map = {}
        self.die2vartype_map = {}
        self.cu_name_map = {}   # maps a CompileUnit object to it's unique display name
        self.enum_die_map = {}
        self.struct_die_map = {}
        self.hierarchical_name_2_memberlist_map = {}
        self.endianness = 'little'

        if filename is not None:
            self.load_from_elf_file(filename)

    def get_varmap(self):
        return self.varmap

    # Builds a dictionary that maps a CompuleUnit object to a unique displayable name
    def make_cu_name_map(self, dwarfinfo):

        fullpath_cu_tuple_list = []
        fullpath_set = set()
        for cu in dwarfinfo.iter_CUs():
            topdie = cu.get_top_DIE()
            if topdie.tag != 'DW_TAG_compile_unit':
                raise Exception('Top die should be a compile unit')

            comp_dir = None
            name = self.get_name(topdie)
            if 'DW_AT_comp_dir' in topdie.attributes:
                comp_dir = topdie.attributes['DW_AT_comp_dir'].value.decode('ascii')
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
    def make_unique_display_name(cls, fullpath_cu_tuple_list):
        displayname_map = {}

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
                            raise Exception('Name too long')
                    except:
                        newname = cuname.make_unique_numbered_name(name_set)

                    name_set.add(newname)

                    if newname not in displayname_map:
                        displayname_map[newname] = []
                    displayname_map[newname].append(cuname)

                del displayname_map[display_name]

        displayname_cu_tuple_list = []
        for displayname in displayname_map:
            displayname_cu_tuple_list.append((displayname, displayname_map[displayname][0].cu))
        return displayname_cu_tuple_list

    def get_cu_name(self, die):
        return self.cu_name_map[die.cu]

    def get_die_at_spec(self, die):
        refaddr = die.attributes['DW_AT_specification'].value + die.cu.cu_offset
        return die.dwarfinfo.get_DIE_from_refaddr(refaddr)

    def get_name(self, die, default=None):
        if 'DW_AT_name' in die.attributes:
            return die.attributes['DW_AT_name'].value.decode('ascii')
        else:
            if default is not None:
                return default
            elif die.tag in self.defaults_names:
                return self.defaults_names[die.tag]
            else:
                raise Exception('Cannot get a name for this die. %s' % die)

    def get_linkage_name(self, die):
        return self.demangler.demangle(die.attributes['DW_AT_linkage_name'].value.decode('ascii'))

    # Tells if the die is accessible from outside the compile unit. If it is, it's global, otherwise it's static.

    def is_external(self, die):
        try:
            return die.attributes['DW_AT_external'].value
        except:
            return False

    def get_core_base_type(self, encoding, bytesize):

        encoding_map = {
            self.DwarfEncoding.DW_ATE_address: {
                # todo
            },
            self.DwarfEncoding.DW_ATE_boolean: {
                1: VariableType.boolean
            },
            self.DwarfEncoding.DW_ATE_complex_float: {
                1: VariableType.cfloat8,
                2: VariableType.cfloat16,
                4: VariableType.cfloat32,
                8: VariableType.cfloat64,
                16: VariableType.cfloat128,
                32: VariableType.cfloat256
            },
            self.DwarfEncoding.DW_ATE_float: {
                1: VariableType.float8,
                2: VariableType.float16,
                4: VariableType.float32,
                8: VariableType.float64,
                16: VariableType.float128,
                32: VariableType.float256

            },
            self.DwarfEncoding.DW_ATE_signed: {
                1: VariableType.sint8,
                2: VariableType.sint16,
                4: VariableType.sint32,
                8: VariableType.sint64,
                16: VariableType.sint128,
                32: VariableType.sint256
            },
            self.DwarfEncoding.DW_ATE_signed_char: {
                1: VariableType.sint8,
                2: VariableType.sint16,
                4: VariableType.sint32,
                8: VariableType.sint64,
                16: VariableType.sint128,
                32: VariableType.sint256
            },
            self.DwarfEncoding.DW_ATE_unsigned: {
                1: VariableType.uint8,
                2: VariableType.uint16,
                4: VariableType.uint32,
                8: VariableType.uint64,
                16: VariableType.uint128,
                32: VariableType.uint256
            },
            self.DwarfEncoding.DW_ATE_unsigned_char: {
                1: VariableType.uint8,
                2: VariableType.uint16,
                4: VariableType.uint32,
                8: VariableType.uint64,
                16: VariableType.uint128,
                32: VariableType.uint256
            },
            self.DwarfEncoding.DW_ATE_UTF: {
                1: VariableType.sint8,
                2: VariableType.sint16,
                4: VariableType.sint32,
            }
        }

        if encoding not in encoding_map:
            raise ValueError('Unknown encoding %s' % encoding)

        if bytesize not in encoding_map[encoding]:
            raise ValueError('Encoding %s with %d bytes' % (encoding, bytesize))

        return encoding_map[encoding][bytesize]

    def load_from_elf_file(self, filename):
        varmap = []
        with open(filename, 'rb') as f:
            elffile = ELFFile(f)

            if not elffile.has_dwarf_info():
                raise Exception('File has no DWARF info')

            self.dwarfinfo = elffile.get_dwarf_info()
            self.endianness = 'little' if elffile.little_endian else 'big'

            self.make_cu_name_map(self.dwarfinfo)
            self.demangler = GccDemangler()  # todo : adapt according to compile unit producer

            for cu in self.dwarfinfo.iter_CUs():
                die = cu.get_top_DIE()
                self.extract_var_recursive(die)

    # Process each die recursively and call the right handler based on the die Tag
    def extract_var_recursive(self, die):
        process_fn = {
            'DW_TAG_base_type': self.die_process_base_type,
            'DW_TAG_variable': self.die_process_variable,
            'DW_TAG_enumeration_type': self.die_process_enum,
            'DW_TAG_enumerator': self.die_process_enum_val
        }

        if die.tag in process_fn:
            process_fn[die.tag](die)

        for child in die.iter_children():
            self.extract_var_recursive(child)

    def get_typename_from_die(self, die):
        return die.attributes['DW_AT_name'].value.decode('ascii')

    # Process die of type "base type". Register the type in the global index and maps it to a known type.
    def die_process_base_type(self, die):
        name = self.get_typename_from_die(die)
        encoding = self.DwarfEncoding(die.attributes['DW_AT_encoding'].value)
        bytesize = die.attributes['DW_AT_byte_size'].value
        basetype = self.get_core_base_type(encoding, bytesize)
        self.varmap.register_base_type(name, basetype)

        self.die2typeid_map[die] = self.varmap.get_type_id(name)
        self.die2vartype_map[die] = basetype

    def die_process_enum(self, die):
        name = self.get_name(die)
        if die not in self.enum_die_map:
            self.enum_die_map[die] = VariableEnum(name)

    def die_process_enum_val(self, die):
        parent_enum = die.get_parent()
        if parent_enum not in self.enum_die_map:
            raise Exception('Encountered an enumerator die with a parent not in enum map')

        name = self.get_name(die)
        if 'DW_AT_const_value' in die.attributes:
            value = die.attributes['DW_AT_const_value'].value
            self.enum_die_map[parent_enum].add_value(name=name, value=value)
        else:
            logging.error('Enumerator without value')

    # Todo: the fucntions below could probably merge in one "type analyzer" function

    def extract_enum(self, die):
        prevdie = die
        while True:
            refaddr = prevdie.attributes['DW_AT_type'].value + prevdie.cu.cu_offset
            nextdie = prevdie.dwarfinfo.get_DIE_from_refaddr(refaddr)
            if nextdie.tag == 'DW_TAG_base_type':
                return None
            elif nextdie.tag == 'DW_TAG_enumeration_type':
                self.die_process_enum(nextdie)
                return self.enum_die_map[nextdie]
            else:
                prevdie = nextdie

    def extract_basetype_die(self, die):
        prevdie = die
        while True:
            refaddr = prevdie.attributes['DW_AT_type'].value + prevdie.cu.cu_offset
            nextdie = prevdie.dwarfinfo.get_DIE_from_refaddr(refaddr)
            if nextdie.tag == 'DW_TAG_base_type':
                return nextdie
            else:
                prevdie = nextdie

    def is_type_struct_or_class(self, die):
        prevdie = die
        while True:
            refaddr = prevdie.attributes['DW_AT_type'].value + prevdie.cu.cu_offset
            nextdie = prevdie.dwarfinfo.get_DIE_from_refaddr(refaddr)

            if nextdie.tag in ['DW_TAG_structure_type', 'DW_TAG_class_type']:
                return True
            elif nextdie.tag == 'DW_TAG_base_type':
                return False

            else:
                prevdie = nextdie

    def get_struct_or_class_type(self, die):
        prevdie = die
        while True:
            refaddr = prevdie.attributes['DW_AT_type'].value + prevdie.cu.cu_offset
            nextdie = prevdie.dwarfinfo.get_DIE_from_refaddr(refaddr)
            if nextdie.tag in ['DW_TAG_structure_type', 'DW_TAG_class_type']:
                return nextdie
            elif nextdie.tag == 'DW_TAG_base_type':
                raise Exception('Not a structure type')
            else:
                prevdie = nextdie

    # When we encounter a struct die, we make a definition that we keep global,
    # this definition includes all submember with their respective offset.
    # each time we will encounter a instance of this struct, we will generate a variable for each sub member

    def die_process_struct(self, die):
        if die not in self.struct_die_map:
            self.struct_die_map[die] = self.get_struct_or_class_def(die)

    # Go down the hierarchy to get the whole struct def in a recursive way
    def get_struct_or_class_def(self, die):
        if die.tag not in ['DW_TAG_structure_type', 'DW_TAG_class_type']:
            raise ValueError('DIE must be a structure or a class type')

        struct = Struct(self.get_name(die))

        for child in die.iter_children():
            if child.tag in ['DW_TAG_structure_type', 'DW_TAG_class_type']:
                self.die_process_struct(child)
            elif child.tag == 'DW_TAG_member':
                member = self.get_member_from_die(child)
                if member is not None:
                    struct.add_member(member)
            elif child.tag == 'DW_TAG_subprogram':
                pass  # TODO : There's a lot of stuff underneath this.
            else:
                raise NotImplementedError('DIE below structure type is expected to be a member or a struct.')  # In case this happens..

        return struct

    # Read a member die and generate a Struct.Member that we will later on use to register a variable.
    # The struct.Member object contains everything we need to map a
    def get_member_from_die(self, die):
        name = self.get_name(die)
        if self.is_type_struct_or_class(die):
            struct_die = self.get_struct_or_class_type(die)
            substruct = self.get_struct_or_class_def(struct_die)  # recursion
            vartype = VariableType.struct
            typename = None
        else:
            basetype_die = self.extract_basetype_die(die)
            self.die_process_base_type(basetype_die)    # Just in case it is unknown yet
            typename = self.get_typename_from_die(basetype_die)
            substruct = None

        # We are looking at a forward declared member.
        if 'DW_AT_declaration' in die.attributes and die.attributes['DW_AT_declaration'].value == True:
            return None

        byte_offset = die.attributes['DW_AT_data_member_location'].value

        if 'DW_AT_bit_offset' in die.attributes:
            if 'DW_AT_byte_size' not in die.attributes:
                raise Exception('Missing DW_AT_byte_size for bitfield %s' % (self.get_name(die, '')))
            if 'DW_AT_bit_size' not in die.attributes:
                raise Exception('Missing DW_AT_bit_size for bitfield %s' % (self.get_name(die, '')))

        bitsize = die.attributes['DW_AT_bit_size'].value if 'DW_AT_bit_size' in die.attributes else None

        # Not sure about this.
        if 'DW_AT_bit_offset' in die.attributes:
            membersize = die.attributes['DW_AT_byte_size'].value
            if self.endianness == 'little':
                bitoffset = (die.attributes['DW_AT_byte_size'].value * 8) - die.attributes['DW_AT_bit_offset'].value - bitsize
            elif self.endianness == 'big':
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
            substruct=substruct
        )

    # We have an instance of a struct. Use the location and go down the structure recursively
    # using the members offsets to find the final address that we will apply to the output var
    def register_struct_var(self, die, location):
        path_segments = self.make_varpath(die)
        path_segments.append(self.get_name(die))
        struct_die = self.get_struct_or_class_type(die)
        struct = self.struct_die_map[struct_die]
        startpoint = Struct.Member(struct.name, is_substruct=True, bitoffset=None, bitsize=None, substruct=struct)

        # Start the recursion
        self.register_member_as_var_recursive(path_segments, startpoint, location, offset=0)

    # Recursive function to dig into a structure and register all possible variables.
    def register_member_as_var_recursive(self, path_segments, member, location, offset):
        if member.is_substruct:
            struct = member.substruct
            for name in struct.members:
                member = struct.members[name]
                new_path_segments = path_segments.copy()
                if member.is_substruct:
                    new_path_segments.append(name)
                    location = location.copy()  # When we go ina substruct, the member byte_offset is reset to 0
                    location.add_offset(member.byte_offset)

                elif member.byte_offset is not None:
                    offset = member.byte_offset

                self.register_member_as_var_recursive(new_path_segments, member, location, offset)
        else:
            location = location.copy()
            location.add_offset(member.byte_offset)

            self.varmap.add_variable(
                path_segments=path_segments,
                name=member.name,
                original_type_name=member.original_type_name,
                location=location,
                bitoffset=member.bitoffset,
                bitsize=member.bitsize,
                # enum                = member.enum # TODO
            )

            # context.varmap.append(varentry)

    # Try to extract a location from a die.

    def get_location(self, die):
        try:
            if 'DW_AT_location' in die.attributes:
                dieloc = (die.attributes['DW_AT_location'].value)

                if not isinstance(dieloc, list):
                    raise ValueError('die location is not a list')

                if len(dieloc) < 1:
                    raise ValueError('die location is too small')

                if dieloc[0] != self.DW_OP_ADDR:
                    raise ValueError('die location must be an absolute address')

                if len(dieloc) < 2:
                    raise ValueError('die location is too small')

                return VariableLocation.from_bytes(dieloc[1:], self.endianness)
        except:
            return None

    # Process a variable die.
    # Register a variable from it.
    def die_process_variable(self, die, location=None):
        if location is None:
            location = self.get_location(die)

        if 'DW_AT_specification' in die.attributes:
            vardie = self.get_die_at_spec(die)
            self.die_process_variable(vardie, location)

        else:
            if location is not None:
                if self.is_type_struct_or_class(die):
                    struct_die = self.get_struct_or_class_type(die)
                    self.die_process_struct(struct_die)
                    self.register_struct_var(die, location)
                else:
                    path_segments = self.make_varpath(die)
                    name = self.get_name(die)
                    basetype_die = self.extract_basetype_die(die)
                    enum_obj = self.extract_enum(die)
                    self.die_process_base_type(basetype_die)
                    self.varmap.add_variable(
                        path_segments=path_segments,
                        name=name,
                        location=location,
                        original_type_name=self.get_typename_from_die(basetype_die),
                        enum=enum_obj
                    )

    def get_varpath_from_hierarchy(self, die):
        segments = []
        parent = die.get_parent()
        while parent is not None:
            if parent.tag == 'DW_TAG_compile_unit':
                break

            try:
                if 'DW_AT_linkage_name' in parent.attributes:
                    name = self.get_linkage_name(parent)
                else:
                    name = self.get_name(parent)
            except:
                if 'DW_AT_specification' in parent.attributes:
                    parent2 = self.get_die_at_spec(parent)
                    name = self.get_name(parent2)

            if name is not None:
                segments.insert(0, name)
            parent = parent.get_parent()
        return segments

    def get_varpath_from_linkage_name(self, die):
        mangled = die.attributes['DW_AT_linkage_name'].value.decode('ascii')
        demangled = self.demangler.demangle(mangled)
        segments = demangled.split('::')
        try:
            name = self.get_name(die)
            if segments[-1] == name:
                segments.pop()
        except:
            pass
        return segments

    def make_varpath(self, die):
        if 'DW_AT_linkage_name' in die.attributes:
            segments = self.get_varpath_from_linkage_name(die)
        else:
            segments = self.get_varpath_from_hierarchy(die)

        if self.is_external(die):
            segments.insert(0, self.GLOBAL)
        else:
            segments.insert(0, self.STATIC)
            segments.insert(1, self.get_cu_name(die))

        return segments
