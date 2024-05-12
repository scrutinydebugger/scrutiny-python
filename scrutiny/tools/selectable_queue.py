__init__ = [
    'SelectEvent',
    'SelectableQueue',
    'QueueSelector'
]

import queue
import threading
from enum import Enum, auto
from typing import List, Optional, Any, TypeVar, Set, Iterable, Generic

T = TypeVar("T")

class SelectEvent(Enum):
    READ = auto()
    WRITE = auto()

class SelectableQueue(Generic[T], queue.Queue[T]):
    _selectors:Set["QueueSelector"]

    def __init__(self, *args:Any, **kwargs:Any) -> None:
        self._selectors = set()
        queue.Queue.__init__(self, *args, **kwargs)

    def _register_selector(self, selector:"QueueSelector") -> None:
        self._selectors.add(selector)
    
    def put(self, item:T, block:bool=True, timeout:Optional[float]=None) -> None:
        queue.Queue.put(self, item, block, timeout)
        for selector in self._selectors:
            selector._notify(self, SelectEvent.WRITE)

    def put_nowait(self, item:T) -> None:
        queue.Queue.put_nowait(self, item)
        for selector in self._selectors:
            selector._notify(self, SelectEvent.WRITE)

    def get(self, block:bool=True, timeout:Optional[float]=None) -> T:
        v = queue.Queue.get(self, block, timeout)
        for selector in self._selectors:
            selector._notify(self, SelectEvent.READ)
        return v

    def get_nowait(self) -> T:
        v = queue.Queue.get_nowait(self)
        for selector in self._selectors:
            selector._notify(self, SelectEvent.READ)
        return v


class QueueSelector:
    _threading_event:threading.Event
    _lock:threading.Lock
    _listened_events:List[SelectEvent]
    _notified_set:Set[SelectableQueue[Any]]

    def __init__(self, queues:List[SelectableQueue[Any]], events:Iterable[SelectEvent]) -> None:
        self._threading_event = threading.Event()
        self._lock = threading.Lock()
        self._listened_events = list(events)
        self._notified_set = set()

        for q in queues:
            q._register_selector(self)

    def _notify(self, q:SelectableQueue[Any], event:SelectEvent) -> None:
        if event in self._listened_events:
            with self._lock:
                self._notified_set.add(q)
                self._threading_event.set()

    def wait(self, timeout:Optional[float]=None) -> Set[SelectableQueue[Any]]:
        self._threading_event.wait(timeout)
        with self._lock:
            self._threading_event.clear()
            outset = self._notified_set.copy()
            self._notified_set.clear()

        return outset
    
    def is_notified(self) -> bool:
        return len(self._notified_set) > 0
