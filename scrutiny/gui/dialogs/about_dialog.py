#    about_dialog.py
#        About window, contains data about the software, including all versions numbers
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QWidget
import PySide6
import PySide6.QtCore
from PySide6.QtCore import Qt
import sys
from typing import Optional

import scrutiny

class AboutDialog(QDialog):
    def __init__(self, parent:Optional[QWidget] = None) -> None:
        super().__init__(parent) 

        self.setWindowTitle("About this software")
        
        # TODO : make pretty
        layout = QFormLayout()
        self.setLayout(layout)
        fields = [
            ("Scrutiny version", scrutiny.__version__),
            ("Python version", "%d.%d.%d" % (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)),
            ("QT version", getattr(PySide6.QtCore, "__version__", "N/A")),
            ("PySide6 version", PySide6.__version__),
        ]

        for i in range(len(fields)):
            property_label = QLabel(fields[i][0])
            value_label = QLabel(fields[i][1])
            layout.addRow(property_label, value_label )

            for label in (property_label, value_label):
                label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

    
    