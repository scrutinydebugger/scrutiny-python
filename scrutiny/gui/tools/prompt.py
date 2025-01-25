#    prompt.py
#        Helper to display errors in standardized fashion
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import os
from pathlib import Path

from PySide6.QtWidgets import QMessageBox, QWidget, QFileDialog
from scrutiny.gui.core.preferences import gui_preferences
from scrutiny.gui import assets
from typing import Optional

def exception_msgbox(parent:QWidget, exception:Exception, title:str, message:str) -> None:
    msgbox = QMessageBox(parent)
    msgbox.setIconPixmap(assets.load_medium_icon_as_pixmap(assets.Icons.Error))
    msgbox.setStandardButtons(QMessageBox.StandardButton.Close)
    msgbox.setWindowTitle(title)
    msgbox.setText(f"{message}.\n {exception.__class__.__name__}: {exception}")
    msgbox.show()


def get_save_filepath_from_last_save_dir(parent:QWidget, extension_with_dot:str, title:str="Save") -> Optional[Path]:
    save_dir = gui_preferences.global_namespace().get_last_save_dir_or_workdir()
    filename, _ = QFileDialog.getSaveFileName(parent, title, str(save_dir), f"*{extension_with_dot}")
    if len(filename) == 0:
        return None     # Cancelled
    gui_preferences.global_namespace().set_last_save_dir(Path(os.path.dirname(filename)))
    if not filename.lower().endswith(extension_with_dot):
        filename += extension_with_dot
    return Path(filename)

def get_save_folderpath_from_last_save_dir(parent:QWidget, title:str="Save", save_dir:Optional[Path]=None) -> Optional[Path]:
    if save_dir is None:
        save_dir = gui_preferences.global_namespace().get_last_save_dir_or_workdir()
    
    foldername = QFileDialog.getExistingDirectory(parent, title, str(save_dir))
    if len(foldername) == 0:
        return None     # Cancelled
    gui_preferences.global_namespace().set_last_save_dir(Path(foldername))
    return Path(foldername)
