#    compileunit.pyi
#        A stub file for the pyelftools package
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

from typing import Dict, Any
from elftools.dwarf.die import DIE



class CompileUnit:
    cu_offset: int
    header:Dict[str, Any]

    def get_top_DIE(self) -> DIE: ...
