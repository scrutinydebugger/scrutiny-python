#    buffered_reader_listener.py
#        Create a listener that simply enqueue the updates in a queue for the user to read
#        it
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['BufferedReaderListener']

from scrutiny.sdk.listeners import ValueUpdate
from . import BaseListener

from queue import SimpleQueue
from typing import List,  Any, Optional

class BufferedReaderListener(BaseListener):
    _queue:"SimpleQueue[ValueUpdate]"
    def __init__(self, *args:Any, **kwargs:Any):
        BaseListener.__init__(self, *args, **kwargs)
        self._queue = SimpleQueue()

    def receive(self, updates: List[ValueUpdate]) -> None:
        for update in updates:
            self._queue.put(update)

    def get_queue(self) -> SimpleQueue:
        """Return the queue used for storage"""
        return self._queue
