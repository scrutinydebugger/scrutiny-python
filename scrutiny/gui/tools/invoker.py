#    invoker.py
#        Some tools to invoke methods across threads in the GUI
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

__all__ = [
    'invoke_later',
    'invoke_in_qt_thread',
    'invoke_in_qt_thread_synchronized'
]

from scrutiny import tools
from scrutiny.gui.core.threads import QT_THREAD_NAME
from scrutiny.tools.thread_enforcer import enforce_thread
from PySide6.QtCore import QObject, Signal, Qt, QTimer
from PySide6.QtWidgets import QApplication

from scrutiny.tools.typing import *


class CrossThreadInvoker(QObject):
    called_signal = Signal()
    _instance: Optional["CrossThreadInvoker"] = None

    @classmethod
    @enforce_thread(QT_THREAD_NAME)
    def init(cls) -> None:
        # Hacky stuff here.
        # Run once in the QT thread. Creates the underlying signal object in the right thread
        # Without this, we can get runtime warning like that "QObject: Cannot create children for a parent that is in a different thread"
        cls.instance().exec(lambda: None)

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
        app = QApplication.instance()
        if app is None:
            raise RuntimeError("A QT application must be running")
        main_thread = app.thread()
        self.moveToThread(main_thread)
        self.setParent(app)

    def exec(self, method: Callable[[], None]) -> None:
        self.called_signal.connect(method, Qt.ConnectionType.SingleShotConnection)
        self.called_signal.emit()


class QueuedInvoker(QObject):
    _instance: Optional["QueuedInvoker"] = None

    @classmethod
    def instance(cls) -> "QueuedInvoker":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        super().__init__()
        app = QApplication.instance()
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
def invoke_later(method: Callable[[], None]) -> None:
    """Enqueue a function to be executed at the back of the event queue"""
    QueuedInvoker.instance().exec(method)


def invoke_in_qt_thread(method: Callable[[], None]) -> None:
    """Runs a function in the QT thread"""
    CrossThreadInvoker.instance().exec(method)


T = TypeVar('T')


def invoke_in_qt_thread_synchronized(method: Callable[[], T], timeout: Optional[int] = None) -> T:
    """Runs a function in the QT thread and wait for its completion. Returns its return value. 
    If an exception is raised in the function, it will be raised in the caller thread"""

    syncer: tools.ThreadSyncer[T] = tools.ThreadSyncer()

    invoke_in_qt_thread(syncer.executor_func(method))
    syncer.finished.wait(timeout)

    if not syncer.finished.is_set():
        raise TimeoutError("Could not run function in QT thread. Timed out")

    if syncer.exception is not None:
        raise syncer.exception

    return cast(T, syncer.return_val)
