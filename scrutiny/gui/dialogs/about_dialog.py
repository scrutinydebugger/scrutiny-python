#    about_dialog.py
#        About window, contains data about the software, including all versions numbers
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from qtpy.QtWidgets import QDialog, QFormLayout, QLabel, QWidget
import qtpy
import qtpy.QtCore
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
            ("qtpy version", qtpy.__version__),
            ("QT API", qtpy.API_NAME),
        ]

        if qtpy.PYQT4 or qtpy.PYQT5 or qtpy.PYQT6:
            fields.append(
                ("PyQT version", qtpy.QtCore.PYQT_VERSION_STR)  # type: ignore
            )
        elif qtpy.PYSIDE6:
            version_str = "unknown"

            try:
                import PySide6
                version_str = PySide6.__version__
            except ImportError:
                pass

            fields.append(
                ("PySide version", version_str)
            )

        for i in range(len(fields)):
            layout.addRow(QLabel(fields[i][0]), QLabel(fields[i][1]) )

    