from typing import Iterable, Dict, Any, Optional


class DwarfInfo:
    def get_DIE_from_refaddr(self, addr: int) -> "Die": pass


class Attribute:
    value: Any


class Die:
    tag: str
    cu: "CompileUnit"
    attributes: Dict[str, Attribute]
    dwarfinfo: DwarfInfo

    def iter_children(self) -> Iterable["Die"]: pass
    def get_parent(self) -> Optional["Die"]: pass


class CompileUnit:
    cu_offset: int

    def get_top_DIE(self) -> "Die": pass


class ELFFile:
    def iter_CUs(self) -> Iterable["CompileUnit"]: pass
