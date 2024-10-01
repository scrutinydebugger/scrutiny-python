from qtpy.QtWidgets import QDialog, QFormLayout, QLabel
import qtpy
import qtpy.QtCore
import sys

import scrutiny

class AboutDialog(QDialog):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

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
                ("PyQT version", qtpy.QtCore.PYQT_VERSION_STR)
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

    