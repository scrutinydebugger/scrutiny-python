from qtpy.QtWidgets import QDialog, QFormLayout, QLabel
from qtpy.QtCore import PYQT_VERSION_STR
import sys

import scrutiny

class AboutDialog(QDialog):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.setWindowTitle("About this software")
        
        # TODO : make pretty
        self.layout = QFormLayout()
        fields = [
            ("Scrutiny version", scrutiny.__version__),
            ("Python version", "%d.%d.%d" % (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)),
            ("PyQT version", PYQT_VERSION_STR),
        ]

        for i in range(len(fields)):
            self.layout.addRow(QLabel(fields[i][0]), QLabel(fields[i][1]) )

        self.setLayout(self.layout)
    