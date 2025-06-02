from typing import Iterable

from elftools.dwarf.die import DIE
from elftools.dwarf.compileunit import CompileUnit

class DWARFInfo:
    def get_DIE_from_refaddr(self, addr: int) -> DIE: ...
    def iter_CUs(self) -> Iterable[CompileUnit]: ...
