#    dwarfinfo.pyi
#        A stub file for the pyelftools package
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

from typing import Iterable

from elftools.dwarf.die import DIE
from elftools.dwarf.compileunit import CompileUnit

class DWARFInfo:
    def get_DIE_from_refaddr(self, addr: int) -> DIE: ...
    def iter_CUs(self) -> Iterable[CompileUnit]: ...
