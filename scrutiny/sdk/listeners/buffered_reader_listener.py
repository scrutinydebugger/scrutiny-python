#    buffered_reader_listener.py
#        Create a listener that simply enqueue the updates in a queue for the user to read
#        them
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

__all__ = ['BufferedReaderListener']

from scrutiny.sdk.listeners import ValueUpdate
from . import BaseListener

import queue
from scrutiny.tools.typing import *


class BufferedReaderListener(BaseListener):
    _queue: "queue.Queue[ValueUpdate]"

    def __init__(self, queue_max_size: int, *args: Any, **kwargs: Any):
        """Creates a listener that makes a copy of every received :class:`ValueUpdate<scrutiny.sdk.listeners.ValueUpdate>` 
        object and push them into a queue, waiting for the user to read them.

        Adding/removing subscriptions while running is allowed

        :param queue_max_size: Queue max size. Updates will be dropped if the queue is not read fast enough and this size is exceeded
        :param args: Passed to :class:`BaseListener<scrutiny.sdk.listeners.BaseListener>`
        :param kwargs: Passed to :class:`BaseListener<scrutiny.sdk.listeners.BaseListener>`
        """
        BaseListener.__init__(self, *args, **kwargs)
        self._queue = queue.Queue(maxsize=queue_max_size)

    def receive(self, updates: List[ValueUpdate]) -> None:
        for update in updates:
            try:
                self._queue.put_nowait(update)
            except queue.Full:
                self._logger.warning("Queue is full. Dropping updates")

    def get_queue(self) -> "queue.Queue[ValueUpdate]":
        """Returns the queue used for storage"""
        return self._queue

    def allow_subscription_changes_while_running(self) -> bool:
        return True
