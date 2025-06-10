__all__ = [
    'ValueUpdate',
    'BaseListener'
]

import abc
from dataclasses import dataclass
from datetime import datetime
import queue
import logging
import threading
import types
import time

from scrutiny.sdk.watchable_handle import WatchableHandle
from scrutiny.tools import validation
from scrutiny.core.logging import DUMPDATA_LOGLEVEL
from scrutiny.sdk import exceptions as sdk_exceptions
from scrutiny.tools.profiling import VariableRateExponentialAverager
from scrutiny import tools
from scrutiny.tools.typing import *


@dataclass(frozen=True)
class ValueUpdate:
    """(Immutable struct) Contains the relevant information about a watchable update broadcast by the server """

    watchable: WatchableHandle
    """A reference to the watchable object that generated the update"""

    value: Union[int, float, bool]
    """Value received in the update"""

    update_timestamp: datetime
    """Timestamp of the update. Taken by the server right after reading the device. Precise to the microsecond"""


class BaseListener(abc.ABC):

    @dataclass(frozen=True)
    class Statistics:
        """(Immutable struct) A data structure containing several useful debugging metrics for a listener"""

        update_received_count: int
        """Total number of value update received by the server. This value can grow very large"""
        update_drop_count: int
        """Number of value update that needed to be dropped because of queue overflow"""
        update_per_sec: float
        """Estimated rate of update/sec averaged of the few seconds"""
        internal_qsize: int
        """Number of element in the internal queue"""

    TARGET_PROCESS_INTERVAL = 0.2

    _name: str
    """Name of the listener for logging"""
    _subscriptions: Set[WatchableHandle]
    """List of watchable to listen for"""
    _subscriptions_lock: threading.Lock
    """A lock used to do subsequent operations on the subscription list"""
    _update_queue: Optional["queue.Queue[Optional[List[ValueUpdate]]]"]
    """Queue of updates moving from the client worker thread to the listener thread"""
    _logger: logging.Logger
    """The logger object"""
    _drop_count: int
    """Number of update dropped"""
    _queue_max_size: int
    """Maximum queue size"""
    _started: bool
    """Flag indicating if the listener thread is started"""
    _thread: Optional[threading.Thread]
    """The listener thread"""
    _setup_error: bool
    """Flag indicating if a an error occured while calling user setup()"""
    _teardown_error: bool
    """Flag indicating if a an error occured while calling user teardown()"""
    _receive_error: bool
    """Flag indicating if a an error occured while calling user receive()"""

    _started_event: threading.Event
    """Event to synchronize start() with its thread."""
    _stop_request_event: threading.Event
    """Event to stop the thread"""
    _update_count: int
    """Number of updates received"""

    _update_rate_measurement: VariableRateExponentialAverager
    """A low pass filter meant to measure the number of value update per seconds that this listener receives"""

    def __init__(self,
                 name: Optional[str] = None,
                 queue_max_size: int = 1000
                 ) -> None:
        """Base abstract class for all listeners. :meth:`receive<receive>` must be overridden.
            :meth:`setup<setup>` and :meth:`teardown<teardown>` can optionally be overridden.

            :param name: Name of the listener used for logging purpose
            :param queue_max_size: Internal queue maximum size. If the queue is ever full, the update notification will be dropped
        """
        if name is None:
            name = self.__class__.__name__
        else:
            name = f'{self.__class__.__name__}[{name}]'
        validation.assert_type(name, 'name', str)

        self._name = name
        self._subscriptions = set()
        self._subscriptions_lock = threading.Lock()
        self._update_queue = None
        self._logger = logging.getLogger(self._name)
        self._drop_count = 0
        self._started_event = threading.Event()
        self._stop_request_event = threading.Event()
        self._started = False
        self._thread = None
        self._setup_error = False
        self._teardown_error = False
        self._receive_error = False
        self._queue_max_size = queue_max_size
        self._update_count = 0
        self._update_rate_measurement = VariableRateExponentialAverager(time_estimation_window=0.1, tau=0.5, near_zero=0.1)

    def _broadcast_update(self, watchables: List[WatchableHandle]) -> None:
        """
            Method called by the client to notify the listener.
            It should be possible for many clients to update the same listener, 
            so this method is expected to be thread safe.
        """
        if self._started:
            update_list: List[ValueUpdate] = []
            with self._subscriptions_lock:
                subscribed_watchables = [w for w in watchables if w in self._subscriptions]
            for watchable in subscribed_watchables:
                if watchable in self._subscriptions:
                    timestamp = watchable.last_update_timestamp
                    if timestamp is None:
                        timestamp = datetime.now()
                    update = ValueUpdate(
                        watchable=watchable,
                        value=watchable.value,
                        update_timestamp=timestamp,
                    )
                    update_list.append(update)

            if len(update_list) > 0 and self._update_queue is not None:
                if self._logger.isEnabledFor(DUMPDATA_LOGLEVEL):    # pragma: no cover
                    self._logger.log(DUMPDATA_LOGLEVEL, f"Received {len(update_list)} updates")
                try:
                    self._update_queue.put_nowait(update_list)
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

    def _thread_task(self) -> None:
        self._logger.debug("Thread started. Calling setup()")
        try:
            self.setup()
        except Exception as e:
            self._setup_error = True
            tools.log_exception(self._logger, e, "User setup() function raise an exception.")
        finally:
            self._started_event.set()

        try:
            if not self._setup_error:
                self._update_rate_measurement.enable()
                self.process()
                last_process_timer = time.perf_counter()
                while not self._stop_request_event.is_set():
                    if self._update_queue is not None:
                        updates: Optional[List[ValueUpdate]] = None
                        try:
                            time_since_process = (time.perf_counter() - last_process_timer)
                            timeout = max(self.TARGET_PROCESS_INTERVAL - time_since_process, 0)
                            updates = self._update_queue.get(block=True, timeout=timeout)
                        except queue.Empty:
                            pass

                        if updates is not None:
                            self._update_count += len(updates)
                            self._update_rate_measurement.add_data(len(updates))
                            self.receive(updates)

                        if time.perf_counter() - last_process_timer >= self.TARGET_PROCESS_INTERVAL:
                            self._update_rate_measurement.update()
                            self.process()
                            last_process_timer = time.perf_counter()

        except Exception as e:
            self._receive_error = True
            tools.log_exception(self._logger, e, "Error in listener thread")
        finally:
            self._update_rate_measurement.disable()
            self._logger.debug("Thread exiting. Calling teardown()")
            try:
                self.teardown()
            except Exception as e:
                self._teardown_error = True
                tools.log_exception(self._logger, e, "User teardown() function raise an exception")

        self._logger.debug("Thread exit")

    def __enter__(self) -> "BaseListener":
        return self

    def __exit__(self,
                 exc_type: Optional[Type[BaseException]],
                 exc_val: Optional[BaseException],
                 exc_tb: Optional[types.TracebackType]
                 ) -> Literal[False]:
        self.stop()
        return False

    def _assert_can_change_subscriptions(self) -> None:
        """Raise an exception if it is not permitted to change the subscription list"""
        if self._started and not self.allow_subscription_changes_while_running():
            raise sdk_exceptions.NotAllowedError("Changing the number of watchable subscription is not allowed when the listener is started")

    def setup(self) -> None:
        """Overridable function called by the listener from its thread when starting, before monitoring"""
        pass

    def teardown(self) -> None:
        """Overridable function called by the listener from its thread when stopping, right after being done monitoring"""
        pass

    def process(self) -> None:
        """Method periodically called inside the listener thread. Does nothing by default"""
        pass

    def subscribe(self, watchables: Union[WatchableHandle, Iterable[WatchableHandle]]) -> None:
        """Add one or many new watchables to the list of monitored watchables. 

        :param watchables: The list of watchables to add to the monitor list

        :raise TypeError: Given parameter not of the expected type
        :raise ValueError: Given parameter has an invalid value
        :raise InvalidValueError: If the watchable handle is not ready to be used (not configured by the server)
        """
#        if self._started:
#            raise sdk_exceptions.OperationFailure("Cannot subscribe a watchable once the listener is started")
        if isinstance(watchables, (WatchableHandle, tools.UnitTestStub)):
            watchables = [watchables]
        validation.assert_is_iterable(watchables, 'watchables')
        for watchable in watchables:
            validation.assert_type(watchable, 'watchable', (WatchableHandle, tools.UnitTestStub))
            watchable._assert_configured()  # Paranoid check.

        with self._subscriptions_lock:
            self._assert_can_change_subscriptions()
            for watchable in watchables:
                self._subscriptions.add(watchable)

    def unsubscribe(self, watchables: Union[WatchableHandle, Iterable[WatchableHandle]]) -> None:
        """Remove one or many watchables from the list of monitored watchables. 

        :param watchables: The list of watchables to remove from the monitor list

        :raise TypeError: Given parameter not of the expected type
        :raise ValueError: Given parameter has an invalid value
        :raise KeyError: Given watchable was not monitored previously
        """
#        if self._started:
#            raise sdk_exceptions.OperationFailure("Cannot subscribe a watchable once the listener is started")
        if isinstance(watchables, WatchableHandle):
            watchables = [watchables]
        validation.assert_is_iterable(watchables, 'watchables')
        for watchable in watchables:
            validation.assert_type(watchable, 'watchable', WatchableHandle)

        with self._subscriptions_lock:
            self._assert_can_change_subscriptions()
            for watchable in watchables:
                self._subscriptions.remove(watchable)

    def unsubscribe_all(self) -> None:
        """Removes all watchables from the monitored list. Does not stop the listener"""
        self._assert_can_change_subscriptions()
        self._subscriptions.clear()

    def start(self) -> "BaseListener":
        """Starts the listener thread. Once started, no more subscription can be added.

        :raise OperationFailure: If an error occur while starting the listener
        """
        self._logger.debug("Start requested")
        if self._started:
            raise sdk_exceptions.OperationFailure("Listener already started")

        self._stop_request_event.clear()
        self._started_event.clear()
        self._setup_error = False
        self._teardown_error = False
        self._receive_error = False
        self._update_count = 0
        self._update_queue = queue.Queue(self._queue_max_size)
        self._thread = threading.Thread(target=self._thread_task, daemon=True)
        self._thread.start()

        self._started_event.wait(2)
        if not self._started_event.is_set():
            self.stop()
            raise sdk_exceptions.OperationFailure("Failed to start listener thread")

        if self._setup_error:
            self.stop()
            raise sdk_exceptions.OperationFailure("Error in listerner setup")
        else:
            self._logger.debug("Started")
            self._started = True

        return self

    def stop(self) -> None:
        """Stops the listener thread"""
        self._logger.debug("Stop requested")
        if self._thread is not None:
            if self._thread.is_alive():
                self._stop_request_event.set()
                if self._update_queue is not None:
                    try:
                        self._update_queue.put_nowait(None)
                    except queue.Full:
                        self._empty_update_queue()
                        try:
                            self._update_queue.put_nowait(None)
                        except queue.Full:
                            self._thread.setDaemon(True)

                self._thread.join(timeout=5)
                if self._thread.is_alive():
                    self._logger.error("Failed to stop the thread")
                    self._thread.setDaemon(True)    # Failed to join

            self._thread = None

        self._empty_update_queue()
        self._update_queue = None

        self._started = False
        self._logger.debug("Stopped")

    def get_subscriptions(self) -> Set[WatchableHandle]:
        """Returns a set with all the watchables that this listener is subscribed to"""
        return self._subscriptions.copy()

    def prune_subscriptions(self) -> None:
        """Release the references to any subscribed watchables that are not being watched anymore"""

        with self._subscriptions_lock:
            self._assert_can_change_subscriptions()
            for handle in self._subscriptions.copy():
                if handle.is_dead:
                    with tools.SuppressException(KeyError):
                        self._subscriptions.remove(handle)

    def allow_subscription_changes_while_running(self) -> bool:
        """Indicate if it is allowed to change the subscription list after the listener is started.
        This method can be overridden.

        The following methods affect the watchable subscription list
         - :meth:`subscribe()<subscribe>`
         - :meth:`unsubscribe()<unsubscribe>`
         - :meth:`unsubscribe_all()<unsubscribe_all>`
         - :meth:`prune_subscriptions()<prune_subscriptions>`

         :return: ``True`` if it is allowed to modify the subscriptions when running. ``False`` otherwise
        """
        return False

    def get_stats(self) -> Statistics:
        """Returns internal performance metrics for debugging purpose"""
        return self.Statistics(
            internal_qsize=self._update_queue.qsize() if self._update_queue is not None else 0,
            update_drop_count=self._drop_count,
            update_per_sec=self._update_rate_measurement.get_value(),
            update_received_count=self._update_count
        )

    def reset_stats(self) -> None:
        """Reset performance metrics that can reset"""
        self._drop_count = 0
        self._update_rate_measurement.reset()
        self._update_count = 0

    @property
    def is_started(self) -> bool:
        """Tells if the listener thread is running"""
        return self._started

    @property
    def name(self) -> str:
        """The name of the listener"""
        return self._name

    @property
    def error_occured(self) -> int:
        """Tells if an error occured while running the listener"""
        return self._setup_error or self._receive_error or self._teardown_error

    @property
    def drop_count(self) -> int:
        """The number of update dropped due to a full internal queue"""
        return self._drop_count

    @property
    def update_count(self) -> int:
        """The number of update received (not dropped)"""
        return self._update_count

    @abc.abstractmethod
    def receive(self, updates: List[ValueUpdate]) -> None:
        """Method called by the listener thread each time the client notifies the listeners for one or many updates

        :param updates: List of updates being broadcast
        """
        raise NotImplementedError("Abstract method")
