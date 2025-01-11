
import typing

if typing.TYPE_CHECKING:
    from scrutiny.gui.gui import ScrutinyQtGUI

def app_settings() -> "ScrutinyQtGUI.Settings":
    from scrutiny.gui.gui import ScrutinyQtGUI
    return ScrutinyQtGUI.instance().settings
