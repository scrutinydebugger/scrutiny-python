#    watchable_handle.py
#        A handle on a watchable element (Variable, Alias, RPV). This handle is created by
#        the client when watching
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2023 Scrutiny Debugger

__all__ = ['WatchableHandle']

import threading
from datetime import datetime
import time

from scrutiny.sdk.definitions import *
from scrutiny.core.basic_types import *
from scrutiny.core.embedded_enum import EmbeddedEnum
import scrutiny.sdk.exceptions as sdk_exceptions
from scrutiny.sdk.write_request import WriteRequest
from scrutiny.tools import validation
from scrutiny.tools.typing import *

if TYPE_CHECKING:
    from scrutiny.sdk.client import ScrutinyClient


ValType = Union[int, float, bool]


class WatchableHandle:
    """A handle to a server watchable element (Variable / Alias / RuntimePublishedValue) that gets updated by the client thread."""

    _client: "ScrutinyClient"   # The client that created this handle
    _display_path: str      # The display path
    _shortname: str         # Name of the last element in the display path
    _configuration: Optional[WatchableConfiguration]

    _lock: threading.Lock   # A lock to access the value
    _status: ValueStatus            # Status of the value. Tells if the value is valid or not and why it is invalid if not

    _value: Optional[ValType]       # Contain the latest value gotten by the client
    _last_value_dt: Optional[datetime]              # Datetime of the last value update by the client
    _last_write_dt: Optional[datetime]  # Datetime of the last completed write on this element
    _update_counter: int    # A counter that gets incremented each time the value is updated

    def __init__(self, client: "ScrutinyClient", display_path: str) -> None:
        self._client = client
        self._display_path = display_path
        self._shortname = display_path.split('/')[-1]
        self._configuration = None
        self._lock = threading.Lock()
        self._update_counter = 0
        self._set_invalid(ValueStatus.NeverSet)

    def __repr__(self) -> str:
        addr = "0x%0.8x" % id(self)
        if self._configuration is None:
            return f'<{self.__class__.__name__} "{self._shortname}" [Unconfigured] at {addr}>'

        return f'<{self.__class__.__name__} "{self._shortname}" [{self._configuration.datatype.name}] at {addr}>'

    def _configure(self, config: WatchableConfiguration) -> None:
        with self._lock:
            self._configuration = config
            self._status = ValueStatus.NeverSet
            self._value = None
            self._last_value_dt = None
            self._update_counter = 0

    def _set_last_write_datetime(self, dt: Optional[datetime] = None) -> None:
        if dt is None:
            dt = datetime.now()

        with self._lock:
            self._last_write_dt = dt

    def _update_value(self, val: ValType, timestamp: Optional[datetime] = None) -> None:
        with self._lock:
            if self._status != ValueStatus.ServerGone:
                self._status = ValueStatus.Valid
                self._value = val
                self._last_value_dt = timestamp if timestamp is not None else datetime.now()
                self._update_counter += 1   # unbound in size in python 3
            else:
                self._value = None

    def _set_invalid(self, status: ValueStatus) -> None:
        assert status != ValueStatus.Valid

        with self._lock:
            self._value = None
            self._status = status

    def _read(self) -> ValType:
        with self._lock:
            val = self._value
            val_status = self._status

        if val is None or val_status != ValueStatus.Valid:
            raise sdk_exceptions.InvalidValueError(f"Value of {self._shortname} is unusable. {val_status._get_error()}")

        return val

    def _write(self, val: Union[ValType, str], parse_enum: bool) -> WriteRequest:
        if parse_enum:
            if not isinstance(val, str):
                raise ValueError(f"Value is not an enum string")
            val = self.parse_enum_val(val)  # check for enum is done inside this
        write_request = WriteRequest(self, val)
        self._client._process_write_request(write_request)
        if not self._client._is_batch_write_in_progress():
            write_request.wait_for_completion()
        return write_request

    def _assert_has_enum(self) -> None:
        if not self.has_enum():
            raise sdk_exceptions.BadEnumError(f"Watchable {self._shortname} has no enum defined")

    def _assert_configured(self) -> None:
        if self._configuration is None:
            raise sdk_exceptions.InvalidValueError("This watchable handle is not ready to be used")

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

    def wait_value(self, value: Union[ValType, str], timeout: float, sleep_interval: float = 0.02) -> None:
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

        if isinstance(value, str):
            value = self.parse_enum_val(value)

        if value < 0 and not self.datatype.is_signed():
            raise ValueError(f"{self._shortname} is unsigned and will never have a negative value as requested")

        t1 = time.monotonic()
        while True:
            if time.monotonic() - t1 > timeout:
                raise sdk_exceptions.TimeoutException(f'Value of {self._shortname} did not set to {value} in {timeout}s')

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

    def has_enum(self) -> bool:
        """Tells if the watchable has an enum associated with it"""
        self._assert_configured()
        assert self._configuration is not None
        return self._configuration.enum is not None

    def get_enum(self) -> EmbeddedEnum:
        """ Returns the enum associated with this watchable

        :raises BadEnumError: If the watchable has no enum assigned
        """
        self._assert_configured()
        assert self._configuration is not None

        self._assert_has_enum()
        assert self._configuration.enum is not None
        return self._configuration.enum.copy()

    def parse_enum_val(self, val: str) -> int:
        """Converts an enum value name (string) to the underlying integer value

        :param val: The enumerator name to convert

        :raises BadEnumError: If the watchable has no enum assigned or the given value is not a valid enumerator
        :raise TypeError: Given parameter not of the expected type
        """
        validation.assert_type(val, 'val', str)
        self._assert_configured()
        assert self._configuration is not None

        self._assert_has_enum()
        assert self._configuration.enum is not None
        if not self._configuration.enum.has_value(val):
            raise sdk_exceptions.BadEnumError(f"Value {val} is not a valid value for enum {self._configuration.enum.name}")

        return self._configuration.enum.get_value(val)

    def write_value_str(self, val: str) -> None:
        """Write a value as a string and let the server parse it to a numerical value.
        Supports true/false, hexadecimal (with 0x prefix), float, int and possibly more. 

        :param val: The string value

        :raise TypeError: Given parameter not of the expected type
        :raise TimeoutException: If the request times out
        :raise OperationFailure: If the request fails for any reason, including an unparsable value.
        """
        validation.assert_type(val, 'val', str)
        self._write(val, parse_enum=False)

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
        self._assert_configured()
        assert self._configuration is not None
        return self._configuration.watchable_type

    @property
    def datatype(self) -> EmbeddedDataType:
        """The data type of the device element pointed by this watchable. (sint16, float32, etc.)"""
        self._assert_configured()
        assert self._configuration is not None
        return self._configuration.datatype

    @property
    def server_id(self) -> str:
        """The unique ID assigned by the server for this watchable"""
        self._assert_configured()
        assert self._configuration is not None
        return self._configuration.server_id

    @property
    def value(self) -> ValType:
        return self._read()

    @value.setter
    def value(self, val: ValType) -> None:
        self._write(val, parse_enum=False)

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
    def value_enum(self) -> str:
        """The value converted to its first enum name (alphabetical order). Returns a string. Can be written with a string"""
        val_int = self.value_int
        self._assert_configured()
        assert self._configuration is not None
        self._assert_has_enum()
        assert self._configuration.enum is not None
        for k in sorted(self._configuration.enum.vals.keys()):
            if self._configuration.enum.vals[k] == val_int:
                return k
        raise sdk_exceptions.InvalidValueError(
            f"Watchable {self._shortname} has value {val_int} which is not a valid enum value for enum {self._configuration.enum.name}")

    @value_enum.setter
    def value_enum(self, val: str) -> None:
        self._write(val, parse_enum=True)

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

    @property
    def is_dead(self) -> bool:
        status = ValueStatus(self._status)  # copy for atomicity
        return status not in (ValueStatus.Valid, ValueStatus.NeverSet)
