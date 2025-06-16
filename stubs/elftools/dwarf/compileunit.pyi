#    compileunit.pyi
#        A stub file for the pyelftools package
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

from typing import Dict, Any
from elftools.dwarf.die import DIE
from elftools.dwarf.dwarfinfo import DWARFInfo


class CompileUnit:
    cu_offset: int
    header:Dict[str, Any]
    dwarfinfo:DWARFInfo

    def get_top_DIE(self) -> DIE: ...
