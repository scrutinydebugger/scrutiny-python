#    invoker.py
#        Some tools to invoke methods across threads in the GUI
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = [
    'InvokeInQtThread',
    'InvokeInQtThreadSynchronized'
]

from typing import Callable, Any, Optional, TypeVar
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication
import threading
from typing import cast

class InvokeInQtThread(QObject):

    called_signal = Signal()
    
    def __init__(self, method: Callable[[], None]) -> None:
        """
        Invokes a method on the main thread. Taking care of garbage collection "bugs".
        """
        super().__init__()
        app =  QApplication.instance()
        if app is None:
            raise RuntimeError("A QT application must be running")
        main_thread = app.thread()
        self.moveToThread(main_thread)
        self.setParent(app)
        self.method = method
        self.called_signal.connect(self.execute)
        self.called_signal.emit()

    def execute(self) -> None:
        self.method()
        self.setParent(None)
        
T = TypeVar('T')
def InvokeInQtThreadSynchronized(method: Callable[[], T], timeout:Optional[int]=None) -> T:
    class CallbackReturn:
        return_val:Optional[T] = None
        exception:Optional[Exception] = None
        finished:threading.Event

        def __init__(self) -> None:
            self.return_val = None
            self.exception = None
            self.finished = threading.Event()

    sync_var = CallbackReturn()
    def wrapper_func() -> None:
        try:
            sync_var.return_val = method()
        except Exception as e:
            sync_var.exception = e
        finally:
            sync_var.finished.set()
    
    InvokeInQtThread(wrapper_func)
    sync_var.finished.wait(timeout)

    if not sync_var.finished.is_set():
        raise TimeoutError("Could not run function in QT thread. Timed out")
    
    if sync_var.exception is not None:
        raise sync_var.exception
    
    return cast(T, sync_var.return_val)
