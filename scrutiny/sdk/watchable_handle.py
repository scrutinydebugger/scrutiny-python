#    watchable_handle.py
#        A handle on a watchable element (Variable, Alias, RPV). This handle is created by
#        the client when watching
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import threading
from datetime import datetime
import time

from scrutiny.sdk.definitions import *
from scrutiny.core.basic_types import *
import scrutiny.sdk.exceptions as sdk_exceptions
from scrutiny.sdk.write_request import WriteRequest
from scrutiny.core import validation
from typing import Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from scrutiny.sdk.client import ScrutinyClient


ValType = Union[int, float, bool]


class WatchableHandle:
    """A handle to a server watchable element (Variable / Alias / RuntimePublishedValue) that gets updated by the client thread."""

    _client: "ScrutinyClient"   # The client that created this handle
    _display_path: str      # The display path
    _shortname: str         # Name of the last element in the display path
    _lock: threading.Lock   # A lock to access the value

    _datatype: EmbeddedDataType     # The datatype represented in the device (uint8, float32, etc)
    _watchable_type: WatchableType  # Tye of watchable : Alias, Variable or RPV
    _server_id: Optional[str]       # The ID assigned by the server
    _status: ValueStatus            # Status of the value. Tells if the value is valid or not and why it is invalid if not

    _value: Optional[ValType]       # Contain the latest value gotten by the client
    _last_value_dt: Optional[datetime]  # Datetime of the last value update by the client
    _last_write_dt: Optional[datetime]  # Datetime of the last completed write on this element
    _update_counter: int    # A counter that gets incremented each time the value is updated

    def __init__(self, client: "ScrutinyClient", display_path: str) -> None:
        self._client = client
        self._display_path = display_path
        self._shortname = display_path.split('/')[-1]
        self._lock = threading.Lock()
        self._update_counter = 0
        self._set_invalid(ValueStatus.NeverSet)

    def __repr__(self) -> str:
        addr = "0x%0.8x" % id(self)
        return f'<{self.__class__.__name__} "{self._shortname}" [{self._datatype.name}] at {addr}>'

    def _configure(self, watchable_type: WatchableType, datatype: EmbeddedDataType, server_id: str) -> None:
        with self._lock:
            self._watchable_type = watchable_type
            self._datatype = datatype
            self._server_id = server_id
            self._status = ValueStatus.NeverSet
            self._value = None
            self._last_value_dt = None
            self._update_counter = 0

    def _set_last_write_datetime(self, dt: Optional[datetime] = None) -> None:
        if dt is None:
            dt = datetime.now()

        with self._lock:
            self._last_write_dt = dt

    def _update_value(self, val: ValType) -> None:
        with self._lock:
            if self._status != ValueStatus.ServerGone:
                self._status = ValueStatus.Valid
                self._value = val
                self._last_value_dt = datetime.now()
                self._update_counter += 1   # unbounded in size in python 3
            else:
                self._value = None

    def _set_invalid(self, status: ValueStatus) -> None:
        assert status != ValueStatus.Valid

        with self._lock:
            self._value = None
            self._status = status
            self._server_id = None
            self._watchable_type = WatchableType.NA
            self._datatype = EmbeddedDataType.NA

    def _is_dead(self) -> bool:
        return self._status != ValueStatus.Valid and self._status != ValueStatus.NeverSet

    def _read(self) -> ValType:
        with self._lock:
            val = self._value
            val_status = self._status

        if val is None or val_status != ValueStatus.Valid:
            raise sdk_exceptions.InvalidValueError(f"Value of {self._shortname} is unusable. {val_status._get_error()}")

        return val

    def _write(self, val: ValType) -> WriteRequest:
        write_request = WriteRequest(self, val)
        self._client._process_write_request(write_request)
        if not self._client._is_batch_write_in_progress():
            write_request.wait_for_completion()
        return write_request

    def unwatch(self) -> None:
        """Stop watching this item by unsubscribing to the server

        :raise NameNotFoundError: If the required path is not presently being watched
        :raise OperationFailure: If the subscription cancellation failed in any way
        """
        self._client.unwatch(self._display_path)

    def wait_update(self, timeout: float, previous_counter: Optional[int] = None, sleep_interval: float = 0.02) -> None:
        """Wait for the value to be updated by the server

        :param timeout: Amount of time to wait for a value update
        :param previous_counter: Optional update counter to use for change detection. Can be set to ``update_counter+N`` to wait for N updates
        :param sleep_interval: Value passed to ``time.sleep`` while waiting

        :raise TypeError: Given parameter not of the expected type
        :raise ValueError: Given parameter has an invalid value
        :raise InvalidValueError: If the watchable becomes invalid while waiting
        :raise TimeoutException: If no value update happens within the given timeout
        """

        timeout = validation.assert_float_range(timeout, 'timeout', minval=0)
        validation.assert_int_range_if_not_none(previous_counter, 'previous_counter', minval=0)

        t1 = time.monotonic()
        entry_counter = self._update_counter if previous_counter is None else previous_counter
        while True:

            if time.monotonic() - t1 > timeout:
                raise sdk_exceptions.TimeoutException(f'Value of {self._shortname} did not update in {timeout}s')

            if self._status != ValueStatus.NeverSet and self._status != ValueStatus.Valid:
                raise sdk_exceptions.InvalidValueError(self._status._get_error())

            if entry_counter != self._update_counter:
                break

            time.sleep(sleep_interval)

    def wait_value(self, value: ValType, timeout: float, sleep_interval: float = 0.02) -> None:
        """ 
        Wait for the watchable to reach a given value. Raises an exception if it does not happen within a timeout value

        :param value: The value that this watchable must have to exit the wait state
        :param timeout: Maximum amount of time to wait for the given value
        :param sleep_interval: Value passed to ``time.sleep`` while waiting

        :raise TypeError: Given parameter not of the expected type
        :raise ValueError: Given parameter has an invalid value
        :raise InvalidValueError: If the watchable becomes invalid while waiting
        :raise TimeoutException: If the watchable value never changes for the given value within the given timeout
        """

        timeout = validation.assert_float_range(timeout, 'timeout', minval=0)
        sleep_interval = validation.assert_float_range(sleep_interval, 'timeout', minval=0)

        if value < 0 and not self.datatype.is_signed():
            raise ValueError(f"{self._shortname} is unsigned and will never have a negative value as requested")

        t1 = time.monotonic()
        while True:
            if time.monotonic() - t1 > timeout:
                raise sdk_exceptions.TimeoutException(f'Value of {self._shortname} did set to {value} in {timeout}s')

            if self.datatype.is_float():
                if float(value) == self.value_float:
                    break
            elif self.datatype.is_integer():
                if int(value) == self.value_int:
                    break
            elif self.datatype == EmbeddedDataType.boolean:
                if bool(value) == self.value_bool:
                    break

            time.sleep(sleep_interval)

    @property
    def display_path(self) -> str:
        """Contains the watchable full tree path"""
        return self._display_path

    @property
    def name(self) -> str:
        """Contains the watchable name, e.g. the basename in the display_path"""
        return self._shortname

    @property
    def type(self) -> WatchableType:
        """The watchable type. Variable, Alias or RuntimePublishedValue"""
        return self._watchable_type

    @property
    def datatype(self) -> EmbeddedDataType:
        """The data type of the device element pointed by this watchable. (sint16, float32, etc.)"""
        return self._datatype

    @property
    def value(self) -> ValType:
        """The last value received for this watchable"""
        return self._read()

    @value.setter
    def value(self, val: ValType) -> None:
        self._write(val)

    @property
    def value_bool(self) -> bool:
        """The value casted as bool"""
        return bool(self.value)

    @property
    def value_int(self) -> int:
        """The value casted as int"""
        return int(self.value)

    @property
    def value_float(self) -> float:
        """The value casted as float"""
        return float(self.value)

    @property
    def last_update_timestamp(self) -> Optional[datetime]:
        """Time of the last value update. ``None`` if not updated at least once. Not reliable for change detection"""
        return self._last_value_dt

    @property
    def last_write_timestamp(self) -> Optional[datetime]:
        """Time of the last successful write operation. ``None`` if never written"""
        return self._last_write_dt

    @property
    def update_counter(self) -> int:
        """Number of value update gotten since the creation of the handle. Can be safely used for change detection"""
        return self._update_counter
