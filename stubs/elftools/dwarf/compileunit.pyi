from typing import Dict, Any
from elftools.dwarf.die import DIE



class CompileUnit:
    cu_offset: int
    header:Dict[str, Any]

    def get_top_DIE(self) -> DIE: ...
