import abc
from dataclasses import dataclass
from datetime import datetime
import queue
import logging
import threading
from typing import Union, List, Set, Iterable,Optional

from scrutiny.core.basic_types import EmbeddedDataType
from scrutiny.sdk.watchable_handle import WatchableHandle
from scrutiny.core import validation
from scrutiny.sdk import exceptions as sdk_exceptions

@dataclass(frozen=True)
class ValueUpdate:
    display_path:str
    datatype:EmbeddedDataType
    value: Union[int, float, bool]
    update_timestamp:datetime


class BaseListeners(abc.ABC):

    _name:str
    _subscriptions:Set[WatchableHandle]
    _update_queue:Optional["queue.Queue[Optional[ValueUpdate]]"]
    _logger:logging.Logger
    _drop_count:int
    _queue_max_size:int
    _started:bool
    _thread:Optional[threading.Thread]

    _started_event:threading.Event
    _stop_request_event:threading.Event

    def __init__(self, name:str, queue_max_size=1000) -> None:
        validation.assert_type(name, 'name', str)

        self._name = name
        self._subscriptions = set()
        self._update_queue = None
        self._logger = logging.getLogger(name)
        self._drop_count = 0
        self._started_event = threading.Event()
        self._started = False
        self._thread = None
        self._queue_max_size=queue_max_size

    def subscribe(self, watchables:Iterable[WatchableHandle]) -> None:
        validation.assert_is_iterable(watchables, 'watchables')
        for watchable in watchables:
            validation.assert_type(watchable, 'watchable', WatchableHandle)
            self._subscriptions.add(watchable)
    
    def _broadcast_update(self, watchable:WatchableHandle) -> None:
        if self._started_event.is_set():
            if watchable in self._subscriptions:
                assert watchable.last_update_timestamp is not None
                update = ValueUpdate(
                    datatype=watchable.datatype,
                    display_path=watchable.display_path,
                    value=watchable.value,
                    update_timestamp=watchable.last_update_timestamp,
                )

                try:
                    self._update_queue.put(update, block=False)
                except queue.Full:
                    self._drop_count += 1
                    must_print = (self._drop_count < 10 or self._drop_count % 10 == 0)
                    if must_print:
                        self._logger.warning(f"Listener queue is full. Dropping update. (Total dropped={self._drop_count})")


    def _empty_update_queue(self) -> None:
        if self._update_queue is not None:
            while not self._update_queue.empty():
                try:
                    self._update_queue.get_nowait()
                except queue.Empty: 
                    break

    def start(self) -> None:
        if self._started:
            raise sdk_exceptions.OperationFailure("Listener already started")
        
        self._stop_request_event.clear()
        self._started_event.clear()
        self.setup()
        self._update_queue = queue.Queue(self._queue_max_size)
        self._thread = threading.Thread(target=self.thread_task)
        self._thread.start()

        self._started_event.wait(2)
        if not self._started_event.is_set():
            raise sdk_exceptions.OperationFailure("Failed to start listener thread")

    def stop(self) -> None:
        if self._thread is not None:
            if self._thread.is_alive():
                self._stop_request_event.set()
                if self._update_queue is not None:
                    try:
                        self._update_queue.put(None, block=False)
                    except queue.Full:
                        self._empty_update_queue()
                        try:
                            self._update_queue.put(None, block=False)
                        except queue.Full:
                            self._thread.setDaemon(True)

                self._thread.join(timeout=5)
                if self._thread.is_alive():
                    self._thread.setDaemon(True)    # Failed to join

            self._thread = None
        
        if self._started:
            self.teardown()
        self._empty_update_queue()
        self._update_queue = None

        self._started = False

    def thread_task(self):
        self._started_event.set()
        while not self._stop_request_event.is_set():
            if self._update_queue is not None:
                update = self._update_queue.get()
                if update is not None:
                    self.receive(update)

    @abc.abstractmethod
    def receive(self, update:ValueUpdate) -> None:
        pass

    @abc.abstractmethod
    def setup(self) -> None:
        pass

    @abc.abstractmethod
    def teardown(self) -> None:
        pass
