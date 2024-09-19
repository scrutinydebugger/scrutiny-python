from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from scrutiny.gui.main_window import MainWindow
from scrutiny.gui import assets
import scrutiny
import ctypes
import platform

class ScrutinyQtGUI:
    
    def run(self, args):
        app = QApplication(args)
        app.setWindowIcon(QIcon(assets.icon()))
        app.setApplicationDisplayName("Scrutiny Debugger")
        app.setApplicationVersion(scrutiny.__version__)
        
        if platform.system() == "Windows":
            # Tells windows that python process host another application. Enables the QT icon in the task bar
            # see https://stackoverflow.com/questions/1551605/how-to-set-applications-taskbar-icon-in-windows-7
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(u'scrutiny.gui.%s' % scrutiny.__version__)

        window = MainWindow()
        window.show()
        return app.exec()
