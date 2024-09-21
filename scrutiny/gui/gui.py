from qtpy.QtWidgets import QApplication
from qtpy.QtGui import QIcon, QPalette
from scrutiny.gui.main_window import MainWindow
from scrutiny.gui import assets
import scrutiny
import ctypes
import platform

class ScrutinyQtGUI:
    debug_layout:bool

    def __init__(self, debug_layout=False):
        self.debug_layout = debug_layout
    
    def load_stylesheet(self, filepath:str, palette):
        color_roles = [
            'WindowText',
            'Button',
            'Light',
            'Midlight',
            'Dark',
            'Mid',
            'Text',
            'BrightText',
            'ButtonText',
            'Base',
            'Window',
            'Shadow',
            'Highlight',
            'HighlightedText',
            'Link',
            'LinkVisited',
            'AlternateBase',
            'NoRole',
            'ToolTipBase',
            'ToolTipText',
            'PlaceholderText',
            'NColorRoles',
        ]

        with open(filepath) as f:
            stylesheet = f.read()
        
        for role in color_roles:
            color = palette.color(getattr(QPalette.ColorRole, role))
            stylesheet = stylesheet.replace(f'@{role}', f"rgb({color.red()},{color.green()}, {color.blue()})")
    
        return stylesheet

    def run(self, args):
        app = QApplication(args)
        app.setWindowIcon(QIcon(str(assets.logo_icon())))
        app.setApplicationDisplayName("Scrutiny Debugger")
        app.setApplicationVersion(scrutiny.__version__)
        stylesheet = self.load_stylesheet(assets.get('stylesheets/scrutiny_base.qss'), app.palette())
        app.setStyleSheet(stylesheet)


        if platform.system() == "Windows":
            # Tells windows that python process host another application. Enables the QT icon in the task bar
            # see https://stackoverflow.com/questions/1551605/how-to-set-applications-taskbar-icon-in-windows-7
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(u'scrutiny.gui.%s' % scrutiny.__version__)

        window = MainWindow()
        if self.debug_layout:
            window.setStyleSheet("border:1px solid red")
        window.show()
        return app.exec()
