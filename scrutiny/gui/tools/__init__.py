
__all__ = ['watchabletype_2_icon']

from scrutiny.sdk import WatchableType
from scrutiny.gui import assets


def watchabletype_2_icon(wt: WatchableType) -> assets.Icons:
    """Return the proper icon for a given watchable type (var, alias, rpv)"""
    if wt == WatchableType.Variable:
        return assets.Icons.Var
    if wt == WatchableType.Alias:
        return assets.Icons.Alias
    if wt == WatchableType.RuntimePublishedValue:
        return assets.Icons.Rpv
    raise NotImplementedError(f"Unsupported icon for {wt}")
