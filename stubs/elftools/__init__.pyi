from typing import Dict, Any, Iterable, Optional


class DWARFInfo:
    def get_DIE_from_refaddr(self, addr: int) -> "Die": ...
    def iter_CUs(self) -> Iterable[CompileUnit]: ...


class Attribute:
    value: Any


class Die:
    tag: str
    cu: "CompileUnit"
    attributes: Dict[str, Attribute]
    dwarfinfo: DWARFInfo
    offset:int

    def iter_children(self) -> Iterable["Die"]: ...
    def get_parent(self) -> Optional["Die"]: ...


class CompileUnit:
    cu_offset: int
    header:Dict[str, Any]

    def get_top_DIE(self) -> "Die": ...
