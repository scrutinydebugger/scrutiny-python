#    invoker.py
#        Some tools to invoke methods across threads in the GUI
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = [
    'InvokeQueued',
    'InvokeInQtThread',
    'InvokeInQtThreadSynchronized'
]

from scrutiny import tools
from scrutiny.gui.core.threads import QT_THREAD_NAME
from scrutiny.tools.thread_enforcer import enforce_thread
from typing import Callable, Optional, TypeVar
from PySide6.QtCore import QObject, Signal, Qt, QTimer
from PySide6.QtWidgets import QApplication

from typing import cast, List

class CrossThreadInvoker(QObject):

    called_signal = Signal()
    _instance:Optional["CrossThreadInvoker"] = None

    @classmethod
    @enforce_thread(QT_THREAD_NAME)
    def init(cls) -> None:
        # Hacky stuff here.
        # Run once in the QT thread. Creates the underlying signal object in the right thread
        # Without this, we can get runtime warning like that "QObject: Cannot create children for a parent that is in a different thread"
        cls.instance().exec(lambda:None)

    @classmethod
    def instance(cls) -> "CrossThreadInvoker":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self) -> None:
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
    
    def exec(self,  method: Callable[[], None]) -> None:
        self.called_signal.connect(method, Qt.ConnectionType.SingleShotConnection)
        self.called_signal.emit()

class QueuedInvoker(QObject):
    _instance:Optional["QueuedInvoker"] = None

    @classmethod
    def instance(cls) -> "QueuedInvoker":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self) -> None:
        super().__init__()
        app =  QApplication.instance()
        if app is None:
            raise RuntimeError("A QT application must be running")
    
    def exec(self, method: Callable[[], None]) -> None:
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(0)

        def exec_method() -> None:
            timer.setParent(None)
            method()

        timer.timeout.connect(exec_method)
        timer.start()


@enforce_thread(QT_THREAD_NAME)
def InvokeQueued(method: Callable[[], None]) -> None:
    """Enqueue a function to be executed at the back of the event queue"""
    QueuedInvoker.instance().exec(method)

def InvokeInQtThread(method: Callable[[], None]) -> None:
    """Runs a function in the QT thread"""
    CrossThreadInvoker.instance().exec(method)

T = TypeVar('T')
def InvokeInQtThreadSynchronized(method: Callable[[], T], timeout:Optional[int]=None) -> T:
    """Runs a function in the QT thread and wait for its completion. Returns its return value. 
    If an exception is raised in the function, it will be raised in the caller thread"""

    sync_var:tools.SyncVar[T] = tools.SyncVar()

    InvokeInQtThread(sync_var.wrapper_func(method))
    sync_var.finished.wait(timeout)

    if not sync_var.finished.is_set():
        raise TimeoutError("Could not run function in QT thread. Timed out")
    
    if sync_var.exception is not None:
        raise sync_var.exception
    
    return cast(T, sync_var.return_val)
