#    __init__.pyi
#        A stub file for the pyelftools package
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

from elftools.dwarf.compileunit import CompileUnit
from elftools.dwarf.dwarfinfo import DWARFInfo

from typing import *

class Section:
    header:Dict[str, Any]

class StringTableSection(Section):
    pass

class SymbolTableSection(Section):
    pass

class SymbolTableIndexSection(Section):
    pass

class SUNWSyminfoTableSection(Section):
    pass

class NullSection(Section):
    pass

class NoteSection(Section):
    pass

class StabSection(Section):
    pass

class ARMAttributesSection(Section):
    pass

class RISCVAttributesSectio(Section):
    pass

class ELFFile:
    def __init__(self, f:BinaryIO) -> None: ...
    def iter_CUs(self) -> Iterable[CompileUnit]: ...
    def get_section_by_name(self, name:str)  -> Section: ...
    def has_dwarf_info(self) -> bool: ...
    def get_dwarf_info(self, relocate_dwarf_sections:bool=True, follow_links:bool=True) -> DWARFInfo:...

    @property
    def little_endian(self) -> bool: ...
    @property
    def stream(self) -> BinaryIO: ...
    @property
    def elfclass(self) -> int: ...
    @property
    def elftype(self) -> Union[str, int]: ...
    @property
    def header(self) -> Dict[Any, Any]: ...
    @property
    def e_ident_raw(self) -> bytes: ...
