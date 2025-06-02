#    signals.py
#        Common tools for signal handling
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['SignalExitHandler']

import signal
import types
import sys
import os
import logging
from scrutiny.tools.typing import *
from scrutiny.tools import log_exception

ExitCallback: TypeAlias = Callable[[], None]


class SignalExitHandler:
    HARD_KILL_SIGNAL_COUNT = 3
    _exit_request: int
    _callback: Optional[ExitCallback]
    _logger: logging.Logger

    def __init__(self, callback: Optional[ExitCallback] = None) -> None:
        self._exit_request = 0
        self._callback = callback
        self._logger = logging.getLogger(self.__class__.__name__)
        signal.signal(signal.SIGINT, self._receive_signal)
        signal.signal(signal.SIGTERM, self._receive_signal)
        if sys.platform == 'win32':
            # Ctrl+break. Used by the GUI to stop the server subprocess.
            # Only signal that works properly on Windows.
            signal.signal(signal.SIGBREAK, self._receive_signal)

    def set_callback(self, callback: ExitCallback) -> None:
        self._callback = callback

    def _receive_signal(self, signum: int, frame: Optional[types.FrameType]) -> None:
        signame = signal.Signals(signum).name
        self._logger.debug(f"Received signal {signame}. Requesting a clean exit.")
        if self._exit_request == 1:
            self._logger.warning(f"Received more than 1 exit signal. This process will die ungracefully after {self.HARD_KILL_SIGNAL_COUNT} signals.")

        if self._exit_request >= self.HARD_KILL_SIGNAL_COUNT:
            self._logger.critical("Received multiple exit signals. Forcefully terminating the process")
            os._exit(1)

        if self._callback is not None:
            try:
                self._callback()
            except Exception as e:
                log_exception(self._logger, e)

        self._exit_request += 1

    def must_exit(self) -> bool:
        return self._exit_request > 0
