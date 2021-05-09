#!/usr/bin/env python

"""
This script parse an ELF file and generate a Scrutiny "Variable Description File" which contains the definition of each 
variables inside the binary in the Scrutiny format.
"""

__author__ = "Pier-Yves Lessard"
__copyright__ = "Copyright 2007, The Cogent Project"
__credits__ = ["Pier-Yves Lessard"]
__license__ = "MIT"
__version__ = "1.0.0"
__maintainer__ = "Pier-Yves Lessard"
__status__ = "Development"


from elftools.elf.elffile import ELFFile
import IPython
import os, sys
from enum import Enum
from demangler import GccDemangler
from icecream import ic
import logging
import re
import json
import jsbeautifier

scrutiny_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(scrutiny_folder)

import core

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(os.path.basename(__file__))
x = 0

die_process_fn = {
    'DW_TAG_base_type'          : 'die_process_base_type', 
    'DW_TAG_variable'           : 'die_process_variable', 
    'DW_TAG_enumeration_type'   : 'die_process_enum', 
    'DW_TAG_enumerator'         : 'die_process_enum_val'
}


defaults_names = {
    'DW_TAG_structure_type' : '<struct>'
}

STATIC = 'static'
GLOBAL = 'global'
MAX_CU_DISPLAY_NAME_LENGTH = 40
DWARF_LOC_ADDR_ID = 3

cu_name_map = {}  # maps a CompileUnit object to it's unique display name
enum_die_map = {}
struct_die_map = {}

class Context:
    def __init__(self, **kwargs):
        for k in kwargs:
            self.__setattr__(k, kwargs[k])


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

class BaseTypeMap:
    NEXT_ID = 0
    def __init__(self):
        self.pair2id_map = {}
        self.die2id_map = {}
        self.id2pair_map = {}

    def register_base_type(self, die, name, vartype):
        pair = (name, vartype)
        if pair not in self.pair2id_map:
            self.pair2id_map[pair] = self.next_id()

        if die in self.die2id_map and self.die2id_map[die] != self.pair2id_map[pair]:
            raise RuntimeError('Base type conflict. ')
        
        self.die2id_map[die] = self.pair2id_map[pair]
        self.id2pair_map[self.pair2id_map[pair]] = pair

    def get_id_from_die(self, die):
        return self.die2id_map[die]

    def get_type_from_die(self, die):
        typeid = self.die2id_map[die]
        pair = self.id2pair_map[typeid]
        return pair[1]


    def get_def(self):
        definition = dict()
        for pair in self.pair2id_map:
            definition[self.pair2id_map[pair]] = dict(name=pair[0], type=pair[1].name)
        return definition

    @classmethod
    def next_id(cls):
        next_id = cls.NEXT_ID
        cls.NEXT_ID +=1
        return next_id

class CuName:
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
            candidate = 'cu%d_%s'% (i, self.filename)
            if candidate not in name_set:
                return candidate
            i+=1


def make_cu_name_map(dwarfinfo):
    
    fullpath_cu_tuple_list = []
    fullpath_set = set()
    for cu in dwarfinfo.iter_CUs():
        topdie = cu.get_top_DIE()
        if topdie.tag != 'DW_TAG_compile_unit':
            raise Exception('Top die should be a compile unit')

        comp_dir = None
        name = get_name(topdie)
        if 'DW_AT_comp_dir' in topdie.attributes:
            comp_dir = topdie.attributes['DW_AT_comp_dir'].value.decode('ascii')
            fullpath = os.path.join(comp_dir, name)
        else:
            fullpath = os.path.abspath(name)

        if fullpath in fullpath_set:
            raise RuntimeError('Duplicate compile unit name')
        fullpath_set.add(fullpath)
        fullpath_cu_tuple_list.append( (fullpath, cu) )

    displayname_cu_tuple_list = make_unique_display_name(fullpath_cu_tuple_list)

    for item in displayname_cu_tuple_list:
        cu_name_map[item[1]] = item[0]


def make_unique_display_name(fullpath_cu_tuple_list):
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
                    if len(newname) > MAX_CU_DISPLAY_NAME_LENGTH:
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
        displayname_cu_tuple_list.append(  (displayname, displayname_map[displayname][0].cu)  )
    return displayname_cu_tuple_list
        

def get_cu_name(die):
    return cu_name_map[die.cu]  

def call_fn(name, *args, **kwargs):
    possibles = globals().copy()
    possibles.update(locals())
    fn = possibles.get(name)
    if not fn:
        raise NotImplementedError("Function %s not implemented" % name)
    return fn( *args, **kwargs)

def get_die_at_spec(die):
    refaddr = die.attributes['DW_AT_specification'].value + die.cu.cu_offset
    return die.dwarfinfo.get_DIE_from_refaddr(refaddr)


def get_name(die, default=None):
    if 'DW_AT_name' in die.attributes:
        return die.attributes['DW_AT_name'].value.decode('ascii')
    else:
        if die.tag in defaults_names:
            return defaults_names[die.tag]
        elif default is not None:
            return default
        else:
            raise Exception('Cannot get a name for this die. %s' % die)

def get_linkage_name(die, context):
    return context.demangler.demangle(die.attributes['DW_AT_linkage_name'].value.decode('ascii'))

# Tells if the die is accessible from outside the compile unit. If it is, it's global, otherwise it's static.
def is_external(die):
    try:
        return die.attributes['DW_AT_external'].value
    except:
        return False

def get_core_base_type(encoding, bytesize):
    if encoding == DwarfEncoding.DW_ATE_boolean:
        if bytesize == 1:
            return core.VariableType.boolean
        else:
            raise NotImplementedError('Boolean with %d bytes' % bytesize)

    elif encoding == DwarfEncoding.DW_ATE_float:
        if bytesize == 4:
            return core.VariableType.float32
        elif bytesize == 8:
            return core.VariableType.float64
        else:
            raise NotImplementedError('Float with %d bytes' % bytesize)

    elif encoding == DwarfEncoding.DW_ATE_signed:
        if bytesize == 1:
            return core.VariableType.sint8
        elif bytesize == 2:
            return core.VariableType.sint16
        elif bytesize == 4:
            return core.VariableType.sint32
        elif bytesize == 8:
            return core.VariableType.sint64
        else:
            raise NotImplementedError('Signed int with %d bytes' % bytesize)

    elif encoding == DwarfEncoding.DW_ATE_signed_char:
        if bytesize == 1:
            return core.VariableType.sint8
        elif bytesize == 2:
            return core.VariableType.sint16
        elif bytesize == 4:
            return core.VariableType.sint32
        elif bytesize == 8:
            return core.VariableType.sint64
        else:
            raise NotImplementedError('Signed char int with %d bytes' % bytesize)

    elif encoding == DwarfEncoding.DW_ATE_unsigned:
        if bytesize == 1:
            return core.VariableType.uint8
        elif bytesize == 2:
            return core.VariableType.uint16
        elif bytesize == 4:
            return core.VariableType.uint32
        elif bytesize == 8:
            return core.VariableType.uint64
        else:
            raise NotImplementedError('Unsigned int with %d bytes' % bytesize)

    elif encoding == DwarfEncoding.DW_ATE_unsigned_char:
        if bytesize == 1:
            return core.VariableType.uint8
        elif bytesize == 2:
            return core.VariableType.uint16
        elif bytesize == 4:
            return core.VariableType.uint32
        elif bytesize == 8:
            return core.VariableType.uint64
        else:
            raise NotImplementedError('Unsigned char int with %d bytes' % bytesize)


def process_file(filename):
    varlist = []
    with open(filename, 'rb') as f:
        elffile = ELFFile(f)

        if not elffile.has_dwarf_info():
            raise Exception('File has no DWARF info')
        
        dwarfinfo = elffile.get_dwarf_info()
        endianness = 'little' if elffile.little_endian else 'big'
        basetype_map = BaseTypeMap()

        make_cu_name_map(dwarfinfo)

        for cu in dwarfinfo.iter_CUs():
            demangler = GccDemangler()  # todo : adapt according to compile unit producer

            context = Context(cu=cu, endianness=endianness, demangler=demangler, varlist=varlist, basetype_map=basetype_map)
            die = cu.get_top_DIE()
            process_die(die, context)

        return {'varlist' : varlist, 'endianness' : endianness, 'basetype_map':basetype_map, 'enum_list' : list(enum_die_map.values())}

# Process each die recursively and call the right handler based on the die Tag
def process_die(die, context):
    if die.tag in die_process_fn:
        fn = die_process_fn[die.tag]
        call_fn(fn, die, context)

    for child in die.iter_children():
        process_die(child, context)


# Process die of type "base type". Register the type in the global index and maps it to a known type.
def die_process_base_type(die, context):
    name = die.attributes['DW_AT_name'].value.decode('ascii')
    encoding = DwarfEncoding(die.attributes['DW_AT_encoding'].value)
    bytesize = die.attributes['DW_AT_byte_size'].value
    basetype = get_core_base_type(encoding, bytesize)
    context.basetype_map.register_base_type(die, name, basetype)

def die_process_enum(die, context):
    name = get_name(die)
    if die not in enum_die_map:
        enum_die_map[die] = core.VariableEnum(name)

def die_process_enum_val(die, context):
    parent_enum = die.get_parent()
    if parent_enum not in enum_die_map:
        raise Exception('Encountered an enumerator die with a parent not in enum map')

    name = get_name(die)
    if 'DW_AT_const_value' in die.attributes:
        value = die.attributes['DW_AT_const_value'].value
        enum_die_map[parent_enum].add_value(name=name, value=value)
    else:
        logger.error('Enumerator without value')


## Todo: the fucntion below could probably merge in one "type analyzer" function
def extract_enum(die, context):
    prevdie = die
    while True:
        refaddr = prevdie.attributes['DW_AT_type'].value + prevdie.cu.cu_offset
        nextdie = prevdie.dwarfinfo.get_DIE_from_refaddr(refaddr)
        if nextdie.tag == 'DW_TAG_base_type':
            return None
        elif nextdie.tag == 'DW_TAG_enumeration_type':
            die_process_enum(nextdie, context)
            return enum_die_map[nextdie]
        else:
            prevdie = nextdie

def extract_basetype_die(die, context):
    prevdie = die
    while True:
        refaddr = prevdie.attributes['DW_AT_type'].value + prevdie.cu.cu_offset
        nextdie = prevdie.dwarfinfo.get_DIE_from_refaddr(refaddr)
        if nextdie.tag == 'DW_TAG_base_type':
            return nextdie
        else:
            prevdie = nextdie

def is_type_struct(die, context):
    prevdie = die
    while True:
        refaddr = prevdie.attributes['DW_AT_type'].value + prevdie.cu.cu_offset
        nextdie = prevdie.dwarfinfo.get_DIE_from_refaddr(refaddr)
        if nextdie.tag == 'DW_TAG_structure_type':
            return True
        elif nextdie.tag == 'DW_TAG_base_type':
            return False
        else:
            prevdie = nextdie

def get_struct_type(die, context):
    prevdie = die
    while True:
        refaddr = prevdie.attributes['DW_AT_type'].value + prevdie.cu.cu_offset
        nextdie = prevdie.dwarfinfo.get_DIE_from_refaddr(refaddr)
        if nextdie.tag == 'DW_TAG_structure_type':
            return nextdie
        elif nextdie.tag == 'DW_TAG_base_type':
            raise Exception('Not a structure type')
        else:
            prevdie = nextdie


def die_process_struct(die, context):
    if die not in struct_die_map:
        struct_die_map[die] = get_struct_def(die, context)

def get_struct_def(die, context):
    if die.tag != 'DW_TAG_structure_type':
        raise ValueError('DIE must be a structure type')

    struct = core.Struct(get_name(die))

    for child in die.iter_children():
        if child.tag == 'DW_TAG_structure_type':
            die_process_struct(child, context)
        elif child.tag == 'DW_TAG_member':
            member = get_member_from_die(child, context)
            struct.add_member(member)
        else:
            raise NotImplementedError('DIE below structure type is expected to be a member or a struct.') # In case this happens..

    return struct

def get_member_from_die(die, context):
    name = get_name(die)
    if is_type_struct(die, context):
        struct_die = get_struct_type(die, context)
        substruct = get_struct_def(struct_die, context) # recursion
        vartype = core.VariableType.struct
        vartype_id = None
    else:
        basetype_die = extract_basetype_die(die, context)
        die_process_base_type(basetype_die, context)    # Just in case it is unknown yet
        vartype_id = context.basetype_map.get_id_from_die(basetype_die)
        vartype = context.basetype_map.get_type_from_die(basetype_die)
        substruct = None

    bitoffset = die.attributes['DW_AT_data_member_location'].value * 8
    if 'DW_AT_bit_offset' in die.attributes:
        if 'DW_AT_byte_size' not in die.attributes:
            raise Exception('Missing DW_AT_byte_size for bitfield %s' % (get_name(die, '')))
       
    bitsize = die.attributes['DW_AT_bit_size'].value if 'DW_AT_bit_size' in die.attributes else None
   
    #Not sure about this.
    if context.endianness == 'little':
        membersize = vartype.get_size_bit()
        if bitsize is not None :
            membersize = bitsize
            bitoffset += (die.attributes['DW_AT_byte_size'].value*8) - die.attributes['DW_AT_bit_offset'].value - membersize
    elif context.endianness == 'big':
       bitoffset += die.attributes['DW_AT_bit_offset'].value 
    else:
        raise ValueError('Unknown endianness')

    return core.Struct.Member(name=name, vartype=vartype, vartype_id=vartype_id, bitoffset = bitoffset, bitsize = bitsize, substruct=substruct)

def register_struct_var(die, context, location):
    path_segments = make_varpath(die, context)
    path_segments.append(get_name(die))
    struct_die = get_struct_type(die, context)
    struct = struct_die_map[struct_die]
    startpoint = core.Struct.Member(struct.name, core.VariableType.struct, bitoffset=None, bitsize=None, substruct=struct)

    register_member_as_var_recursive(path_segments, context, startpoint, location, offset=0)

def register_member_as_var_recursive(path_segments, context, member, location, offset):
    if member.vartype == core.VariableType.struct:
        struct = member.substruct
        for name in struct.members:
            member = struct.members[name]
            new_path_segments = path_segments.copy()
            if member.vartype == core.VariableType.struct:
                new_path_segments.append(name)
                offset += member.bitoffset

            register_member_as_var_recursive(new_path_segments, context, member, location, offset)
    else:
        varentry = core.Variable(
            path_segments   = path_segments, 
            name            = member.name, 
            vartype_id      = member.vartype_id, 
            vartype         = member.vartype, 
            location        = location, 
            endianness      = context.endianness, 
            bitoffset       = offset + member.bitoffset,
            bitsize         = member.bitsize,
            enum            = None  # todo
            )

        context.varlist.append(varentry)


def get_location(die, context):
    try:
        if 'DW_AT_location' in die.attributes:
            dieloc = (die.attributes['DW_AT_location'].value)
            
            if not isinstance(dieloc, list):
                raise ValueError('die location is not a list')

            if len(dieloc) < 1:
                raise ValueError('die location is too small')

            if dieloc[0] != DWARF_LOC_ADDR_ID:
                raise ValueError('die location must be an absolute address')

            if len(dieloc) < 2:
                raise ValueError('die location is too small')

            return core.VariableLocation.from_bytes(dieloc[1:], context.endianness)
    except:
        return None        

def die_process_variable(die, context, location=None):
    if location is None:
        location = get_location(die, context)

    if 'DW_AT_specification' in die.attributes:
        vardie = get_die_at_spec(die)
        die_process_variable(vardie, context, location)

    else:
        if location is not None:
              
            if is_type_struct(die, context):
                struct_die = get_struct_type(die, context)
                die_process_struct(struct_die, context)
                register_struct_var(die, context, location)
            else:
                path_segments = make_varpath(die, context)
                name = get_name(die)  
                basetype_die = extract_basetype_die(die, context)
                enum_obj = extract_enum(die, context)
                die_process_base_type(basetype_die, context)
                vartype_id = context.basetype_map.get_id_from_die(basetype_die)
                vartype = context.basetype_map.get_type_from_die(basetype_die)

                varentry = core.Variable(path_segments=path_segments, name=name, vartype_id=vartype_id, vartype=vartype, location=location, endianness=context.endianness, enum=enum_obj)
                context.varlist.append(varentry)

def get_varpath_from_hierarchy(die, context):
    segments = []
    parent = die.get_parent()
    while parent is not None:
        if parent.tag == 'DW_TAG_compile_unit':
            break

        try:
            if 'DW_AT_linkage_name' in parent.attributes:
                name = get_linkage_name(parent, context)
            else:
                name = get_name(parent)
        except:
            if 'DW_AT_specification' in parent.attributes:
                parent2 = get_die_at_spec(parent)
                name = get_name(parent2)

        if name is not None:
            segments.insert(0, name)
        parent = parent.get_parent()
    return segments

def get_varpath_from_linkage_name(die, context):
    mangled = die.attributes['DW_AT_linkage_name'].value.decode('ascii')
    demangled = context.demangler.demangle(mangled)
    segments = demangled.split('::')
    try:
        name = get_name(die)
        if segments[-1] == name:
            segments.pop()
    except:
        pass
    return segments

def make_varpath(die, context):
    if 'DW_AT_linkage_name' in die.attributes:
        segments = get_varpath_from_linkage_name(die, context)
    else:
        segments = get_varpath_from_hierarchy(die, context)
        
    if is_external(die):
        segments.insert(0, GLOBAL)
    else:
        segments.insert(0, STATIC)
        segments.insert(1, get_cu_name(die))

    return segments

def build_output_struct(filecontent):
    varlist = filecontent['varlist']
    basetype_map = filecontent['basetype_map']
    enum_list = filecontent['enum_list']
    struct = {}

    struct['endianness'] = filecontent['endianness']
    struct['type_map'] = basetype_map.get_def()
    struct['enums'] = {}
    struct['variables'] = {}
    for var in varlist:
        struct['variables'][var.get_fullname()] = var.get_def()

    for enum in enum_list:
        struct['enums'][enum.get_id()] = enum.get_def()

    return struct


def elf2vardesc(filename):
    file_content = process_file(filename)
    output_struct = build_output_struct(file_content)
    return (jsbeautifier.beautify(json.dumps(output_struct)))

if __name__ == '__main__':
    print(elf2vardesc(sys.argv[1]))

