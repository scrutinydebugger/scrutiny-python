#    dwarfinfo.pyi
#        A stub file for the pyelftools package
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

from typing import Iterable, NamedTuple

from elftools.dwarf.die import DIE
from elftools.dwarf.compileunit import CompileUnit

class DwarfConfig(NamedTuple):
    little_endian:bool
    machine_arch:str
    default_address_size:int

class DWARFInfo:
    config:DwarfConfig
    
    def get_DIE_from_refaddr(self, addr: int) -> DIE: ...
    def iter_CUs(self) -> Iterable[CompileUnit]: ...
