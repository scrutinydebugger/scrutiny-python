from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QToolBar,
    QDialog,
    QLabel,
    QFormLayout,
    QGridLayout
)
import qdarktheme

import scrutiny
from scrutiny.gui import assets
import sys

from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QSize, Qt, QRect , PYQT_VERSION_STR

from PyQt6.QtWidgets import QMainWindow


class MainWindow(QMainWindow):
    INITIAL_W = 1200
    INITIAL_H = 900

    def __init__(self):
        super().__init__()
        qdarktheme.setup_theme()

        self.setWindowTitle('Scrutiny Debugger')
        self.setGeometry(self.centered(self.INITIAL_W, self.INITIAL_H))
        self.setWindowState(Qt.WindowState.WindowMaximized)

        
        self.make_menubar()
        

        status_bar = self.statusBar()
        status_bar.addWidget(QLabel("hello"))

    def make_menubar(self) -> None:
        menu_bar = self.menuBar()
        dashboard_menu = menu_bar.addMenu('Dashboard')
        dashboard_menu.addMenu("Open")
        dashboard_menu.addMenu("Save")
        dashboard_menu.addMenu("Clear")

        server_menu = menu_bar.addMenu('Server')
        server_menu.addAction("Configure")
        server_menu = menu_bar.addMenu('Device')
        server_menu.addMenu("Configure")

        info_menu = menu_bar.addMenu("Info")
        show_about_action = QAction("About this software", self)
        show_about_action.triggered.connect(self.show_about)
        info_menu.addAction(show_about_action)
    
    def centered(self, w:int, h:int) -> QRect:
        """Returns a rectangle centered in the screen of given width/height"""
        return QRect(
            max((self.screen().geometry().width() - w), 0) // 2,
            max((self.screen().geometry().height() - h), 0) // 2,
            w,h)

    def show_about(self) -> None:
        ABOUT_W = 400
        ABOUT_H = 200

        dialog = QDialog(self)
        dialog.setWindowTitle("About this software")
        dialog.setGeometry(self.centered(ABOUT_W, ABOUT_H))
        dialog.setSizeGripEnabled(False)
        
        # TODO : make pretty
        layout = QFormLayout()
        fields = [
            ("Scrutiny version", scrutiny.__version__),
            ("Python version", "%d.%d.%d" % (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)),
            ("PyQT version", PYQT_VERSION_STR),
        ]

        for i in range(len(fields)):
            layout.addRow(QLabel(fields[i][0]), QLabel(fields[i][1]) )

        dialog.setLayout(layout)
        dialog.show()
        
