from PySide6.QtWidgets import QMessageBox, QWidget

def exception_msgbox(parent:QWidget, title:str, message:str, exception:Exception) -> None:
    msgbox = QMessageBox(parent)
    msgbox.setStandardButtons(QMessageBox.StandardButton.Close)
    msgbox.setWindowTitle(title)
    msgbox.setText(f"{message}.\n {exception.__class__.__name__}:{exception}")
    msgbox.show()
