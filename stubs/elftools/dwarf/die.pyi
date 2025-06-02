from typing import Dict, Iterable, Optional

from elftools import  Attribute
from elftools.dwarf.dwarfinfo import DWARFInfo
from elftools.dwarf.compileunit import CompileUnit

class DIE:
    tag: str
    cu: CompileUnit
    attributes: Dict[str, Attribute]
    dwarfinfo: DWARFInfo
    offset:int

    def iter_children(self) -> Iterable[DIE]: ...
    def get_parent(self) -> Optional[DIE]: ...
