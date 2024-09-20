from qtpy.QtWidgets import (
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
    QGridLayout,
    QCommonStyle,
    QSizePolicy
)
import qdarktheme


from qtpy.QtGui import  QAction, QPalette, QColor
from qtpy.QtCore import Qt, QRect
from qtpy.QtWidgets import QMainWindow

from scrutiny.gui import assets
from scrutiny.gui.qtads import QtAds    #Advanced Docking System
from scrutiny.gui.dialogs.about_dialog import AboutDialog


class MainWindow(QMainWindow):
    INITIAL_W = 1200
    INITIAL_H = 900
    SIDEBAR_W = 64
    
    SIDEBAR_BUTTON_W = SIDEBAR_W
    SIDEBAR_BUTTON_H = 48

    def __init__(self):
        super().__init__()

        self.setWindowTitle('Scrutiny Debugger')
        self.setGeometry(self.centered(self.INITIAL_W, self.INITIAL_H))
        self.setWindowState(Qt.WindowState.WindowMaximized)

        
        self.make_menubar()
        self.make_main_zone()
        self.make_status_bar()


    def make_menubar(self) -> None:
        menu_bar = self.menuBar()
        dashboard_menu = menu_bar.addMenu('Dashboard')
        dashboard_menu.addAction("Open")
        dashboard_menu.addAction("Save")
        dashboard_menu.addAction("Clear")

        server_menu = menu_bar.addMenu('Server')
        server_menu.addAction("Configure")
        server_menu.addAction("Launch local")
        server_menu = menu_bar.addMenu('Device')
        server_menu.addAction("Configure")

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
        dialog = AboutDialog(self)
        dialog.setGeometry(self.centered(400, 200))
        dialog.show()
        
    def make_main_zone(self) -> None:
        from scrutiny.gui.tools import DiagnosticStyle
        self.central_widget = QWidget()
        self.central_widget.setContentsMargins(0,0,0,0)
        self.setCentralWidget(self.central_widget)
        
        hlayout = QHBoxLayout(self.central_widget)
        hlayout.setContentsMargins(0,0,0,0)
        
        self.sidebar = self.make_sidebar()
        self.sidebar.setContentsMargins(0,0,0,0)
        
        self.dock_conainer = QWidget()
        dock_vlayout = QVBoxLayout(self.dock_conainer)
        dock_vlayout.setContentsMargins(0,0,0,0)
        self.dock_manager = QtAds.CDockManager(self.dock_conainer)
        hlayout.addWidget(self.sidebar)
        hlayout.addWidget(self.dock_conainer)
        dock_vlayout.addWidget(self.dock_manager)
        
        
        l = QLabel()
        l.setWordWrap(True)
        l.setContentsMargins(0,0,0,0)
        l.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        l.setText("Lorem ipsum dolor sit amet, consectetuer adipiscing elit. ")

        dock_widget = QtAds.CDockWidget("Label 1")
        dock_widget.setWidget(l)

        self.dock_manager.addDockWidget(QtAds.TopDockWidgetArea, dock_widget)
    
    def get_central_widget(self) -> QWidget:
        return self.central_widget

    def make_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(self.SIDEBAR_W)
        layout = QVBoxLayout(sidebar)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setContentsMargins(0,0,0,0)

        label_A = QLabel("AAA")
        label_A.setFixedHeight(self.SIDEBAR_BUTTON_H)
        label_A.setFixedWidth(self.SIDEBAR_BUTTON_W)
        label_A.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        label_B = QLabel("BBB")
        label_B.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        label_B.setFixedHeight(self.SIDEBAR_BUTTON_H)
        label_A.setFixedWidth(self.SIDEBAR_BUTTON_W)
        layout.addWidget(label_A)
        layout.addWidget(label_B)

        return sidebar

    def make_status_bar(self) -> None:
        self.status_bar = self.statusBar()
        self.status_bar.addWidget(QLabel("hello"))
