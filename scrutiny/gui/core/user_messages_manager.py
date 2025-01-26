
__all__ = ['UserMessagesManager']

from dataclasses import dataclass
import time
import logging

from scrutiny.gui.core.threads import QT_THREAD_NAME
from scrutiny.tools.thread_enforcer import enforce_thread
from scrutiny.tools.typing import *
from scrutiny.gui.tools.invoker import InvokeInQtThread

from PySide6.QtCore import QObject, Signal, QTimer

class UserMessagesManager:
    """A manager that handles many toast-like messages with a duration but only shows one at the time.
    Meant to be connected to the status bar and exposed to the app as a service
    """
    _instance:Optional["UserMessagesManager"] = None
    @classmethod
    def instance(cls) -> Self:
        if cls._instance is None:
            cls._instance = UserMessagesManager()
        return cls._instance
    
    class _Signals(QObject):
        show_message=Signal(str)
        clear_message=Signal()

    @dataclass
    class Message:
        id:str
        text:str
        end_of_life:float

    _message_queue:List[Message]
    _signals:_Signals
    _message_active:bool
    _timer:QTimer
    _logger = logging.Logger

    def __init__(self) -> None:
        self._message_queue = []
        self._signals = self._Signals()
        self._message_active = False
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._logger = logging.getLogger(self.__class__.__name__)
        self._timer.timeout.connect(self._timer_slot)

    @property
    def signals(self) -> _Signals:
        return self._signals

    def register_message_thread_safe(self, id:str, text:str, lifetime:float) -> None:
        def func() -> None:
            self.register_message(id, text, lifetime)
        InvokeInQtThread(func)

    def clear_message_thread_safe(self, id:str) -> None:
        def func() -> None:
            self.clear_message(id)
        InvokeInQtThread(func)

    @enforce_thread(QT_THREAD_NAME)
    def register_message(self, id:str, text:str, lifetime:float) -> None:
        # Remove other messages with the same ID
        self.clear_message(id)
        
        msg = self.Message(
            id=id,
            text=text,
            end_of_life = time.monotonic() + lifetime
        )

        self._message_queue.append(msg)

        self._update_message_queue()
    
    enforce_thread(QT_THREAD_NAME)
    def clear_message(self, id) -> None:
        i = 0
        while True:
            if i >= len(self._message_queue):
                break

            if self._message_queue[i].id == id:
                del self._message_queue[i]
                if i==0 and self._message_active:
                    self._clear_active()
            else:
                i += 1


    def _clear_active(self) -> None:
        assert self._message_active
        #self._logger.debug("Clearing active message")
        self._signals.clear_message.emit()
        self._message_active = False
        self._timer.stop()


    def _update_message_queue(self) -> None:
        # First we remove expired messages
        i=0
        while True:
            if i >= len(self._message_queue):
                break
            if self._message_queue[i].end_of_life < time.monotonic():
                del self._message_queue[i]
                if i==0 and self._message_active:
                    self._clear_active()
            else:
                i += 1

        if self._message_active == False and len(self._message_queue) > 0:
            self._message_active = True
            msg = self._message_queue[0]
            interval = int(max(0, msg.end_of_life - time.monotonic()) * 1000)
            #self._logger.debug(f"Showing new message. Lifetime: {interval} ms")
            self._signals.show_message.emit(msg.text)
            self._timer.setInterval(interval)
            self._timer.start()
            

    def _timer_slot(self) -> None:
        if self._message_active and len(self._message_queue) > 0:
            del self._message_queue[0]
            self._clear_active()
        self._update_message_queue()
        