from qtpy.QtWidgets import QApplication
from qtpy.QtGui import QIcon
from scrutiny.gui.main_window import MainWindow
from scrutiny.gui import assets
import scrutiny
import ctypes
import platform

from scrutiny.gui.tools import DiagnosticStyle

class ScrutinyQtGUI:
    diagnostic_mode:bool

    def __init__(self, diagnostic_mode=False):
        self.diagnostic_mode = diagnostic_mode
    
    def run(self, args):
        app = QApplication(args)
        app.setWindowIcon(QIcon(assets.icon()))
        app.setApplicationDisplayName("Scrutiny Debugger")
        app.setApplicationVersion(scrutiny.__version__)

        if self.diagnostic_mode:
            app.setStyle(DiagnosticStyle()) # TODO: Doesn't work well
        
        if platform.system() == "Windows":
            # Tells windows that python process host another application. Enables the QT icon in the task bar
            # see https://stackoverflow.com/questions/1551605/how-to-set-applications-taskbar-icon-in-windows-7
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(u'scrutiny.gui.%s' % scrutiny.__version__)

        window = MainWindow()
        window.setStyle
        window.show()
        return app.exec()
