#    about_dialog.py
#        About window, contains data about the software, including all versions numbers
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from PyQt5.QtWidgets import QDialog, QFormLayout, QLabel, QWidget
from PyQt5.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
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
            ("QT version", QT_VERSION_STR),
            ("PyQt5 version", PYQT_VERSION_STR),
        ]

        for i in range(len(fields)):
            layout.addRow(QLabel(fields[i][0]), QLabel(fields[i][1]) )

    