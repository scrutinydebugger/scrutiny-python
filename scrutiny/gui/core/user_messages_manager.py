#    user_messages_manager.py
#        A manager that handles many toast-like messages with a duration but only shows one
#        at the time.
#        Meant to be connected to the status bar and exposed to the app as a service
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['UserMessagesManager']

import time
import logging

from scrutiny.gui.core.threads import QT_THREAD_NAME
from scrutiny.tools.thread_enforcer import enforce_thread
from scrutiny.tools.typing import *
from scrutiny.gui.tools.invoker import invoke_in_qt_thread

from PySide6.QtCore import QObject, Signal, QTimer


class UserMessage(QObject):
    id: str
    text: str
    end_of_life: float
    repeat_counter: int

    def __init__(self, id: str, text: str, end_of_life: float, repeat_counter: int) -> None:
        super().__init__()
        self.id = id
        self.text = text
        self.end_of_life = end_of_life
        self.repeat_counter = repeat_counter


class UserMessagesManager:
    """A manager that handles many toast-like messages with a duration but only shows one at the time.
    Meant to be connected to the status bar and exposed to the app as a service
    """
    _instance: Optional["UserMessagesManager"] = None

    @classmethod
    def instance(cls) -> "UserMessagesManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    class _Signals(QObject):
        show_message = Signal(UserMessage)
        clear_message = Signal()

    _message_queue: List[UserMessage]
    """The message queue. The message at index 0 is the only one that can be active"""
    _signals: _Signals
    """The public signals"""
    _message_active: bool
    """``True`` When the message at index 0 has been announce with signal.show_message"""
    _timer: QTimer
    """The timer used to trigger the end of life of a message"""
    _logger: logging.Logger
    """Logger for debug mainly"""
    _active_msg_counter: int
    """A counter for repetitive message used to add a prefix to a message so the user knows it gets re-emitted"""

    def __init__(self) -> None:
        self._message_queue = []
        self._signals = self._Signals()
        self._message_active = False
        self._active_msg_counter = 1    # Starts at one. meant to be displayed to a human
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._logger = logging.getLogger(self.__class__.__name__)
        self._timer.timeout.connect(self._timer_slot)

    @property
    def signals(self) -> _Signals:
        return self._signals

    def register_message_thread_safe(self, id: str, text: str, lifetime: float) -> None:
        def func() -> None:
            self.register_message(id, text, lifetime)
        invoke_in_qt_thread(func)

    def clear_message_thread_safe(self, id: str) -> None:
        def func() -> None:
            self.clear_message(id)
        invoke_in_qt_thread(func)

    @enforce_thread(QT_THREAD_NAME)
    def register_message(self, id: str, text: str, lifetime: float) -> None:
        # Remove other messages with the same ID
        repeating_message = False
        if self._message_active and len(self._message_queue) > 0:
            if self._message_queue[0].id == id:
                repeating_message = True

        if repeating_message:
            self._active_msg_counter += 1
        else:
            self._active_msg_counter = 1

        self.clear_message(id)

        msg = UserMessage(
            id=id,
            text=text,
            end_of_life=time.monotonic() + lifetime,
            repeat_counter=self._active_msg_counter
        )

        self._message_queue.append(msg)
        self._update_message_queue()

    enforce_thread(QT_THREAD_NAME)

    def clear_message(self, id: str) -> None:
        """Remove any message in the message queue with the specified id.
        If the message is presently active, clear it properly by emitting a signal"""
        i = 0
        while True:
            if i >= len(self._message_queue):
                break

            if self._message_queue[i].id == id:
                del self._message_queue[i]
                if i == 0 and self._message_active:
                    self._clear_active()
            else:
                i += 1

    def _clear_active(self) -> None:
        """Clear the active message. Emit a clear_message signal to the rest of the app"""
        assert self._message_active
        # self._logger.debug("Clearing active message")
        self._signals.clear_message.emit()
        self._message_active = False
        self._timer.stop()

    def _update_message_queue(self) -> None:
        """Maintenance of the message queue. Remove expired messages and make the queue move forward"""

        # First we remove expired messages
        i = 0
        while True:
            if i >= len(self._message_queue):
                break
            if self._message_queue[i].end_of_life < time.monotonic():
                del self._message_queue[i]
                if i == 0 and self._message_active:
                    self._clear_active()
            else:
                i += 1

        # Move the queue forward and broadcast the message
        if self._message_active == False and len(self._message_queue) > 0:
            self._message_active = True
            msg = self._message_queue[0]
            interval = int(max(0, msg.end_of_life - time.monotonic()) * 1000)
            # self._logger.debug(f"Showing new message. Lifetime: {interval} ms")
            self._signals.show_message.emit(msg)
            self._timer.setInterval(interval)
            self._timer.start()

    def _timer_slot(self) -> None:
        if self._message_active and len(self._message_queue) > 0:
            del self._message_queue[0]
            self._clear_active()
        self._update_message_queue()
