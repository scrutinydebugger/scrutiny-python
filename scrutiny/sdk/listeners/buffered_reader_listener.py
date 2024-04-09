#    buffered_reader_listener.py
#        Create a listener that simply enqueue the updates in a queue for the user to read
#        them
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
        """Creates a listener that makes a copy of every received :class:`ValueUpdate<scrutiny.sdk.listeners.ValueUpdate>` 
        object and push them into a queue, waiting for the user to read them.

        :param args: Passed to :class:`BaseListener<scrutiny.sdk.listeners.BaseListener>`
        :param kwargs: Passed to :class:`BaseListener<scrutiny.sdk.listeners.BaseListener>`
        """
        BaseListener.__init__(self, *args, **kwargs)
        self._queue = SimpleQueue()

    def receive(self, updates: List[ValueUpdate]) -> None:
        for update in updates:
            self._queue.put(update)

    def get_queue(self) -> "SimpleQueue[ValueUpdate]":
        """Returns the queue used for storage"""
        return self._queue
