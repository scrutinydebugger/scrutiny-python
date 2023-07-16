
import threading
from datetime import datetime
import time

from scrutiny.sdk.definitions import *
from scrutiny.core.basic_types import *
import scrutiny.sdk.exceptions as sdk_exceptions
from scrutiny.sdk.write_request import WriteRequest
from typing import *

if TYPE_CHECKING:
    from scrutiny.sdk.client import ScrutinyClient


ValType = Union[int, float, bool]


class WatchableHandle:
    _client: "ScrutinyClient"
    _display_path: str
    _shortname: str
    _lock: threading.Lock

    _datatype: EmbeddedDataType
    _watchable_type: WatchableType
    _server_id: Optional[str]
    _status: ValueStatus

    _value: Optional[ValType]
    _last_value_dt: Optional[datetime]
    _last_write_dt: Optional[datetime]
    _update_counter: int

    def __init__(self, client: "ScrutinyClient", display_path: str):
        self._client = client
        self._display_path = display_path
        self._shortname = display_path.split('/')[-1]
        self._lock = threading.Lock()
        self._update_counter = 0
        self._set_invalid(ValueStatus.NeverSet)

    def __repr__(self):
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

    def _set_invalid(self, status: ValueStatus):
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
            if val_status == ValueStatus.NeverSet:
                reason = 'Never set'
            elif val_status == ValueStatus.ServerGone:
                reason = "Server has gone away"
            elif val_status == ValueStatus.DeviceGone:
                reason = "Device has been disconnected"
            elif val_status == ValueStatus.SFDUnloaded:
                reason = "Firmware Description File has been unloaded"
            elif val_status == ValueStatus.NotWatched:
                reason = "Not watched"
            else:
                raise RuntimeError(f"Unknown value status {val_status}")
            raise sdk_exceptions.InvalidValueError(f"Value of {self._shortname} is unusable. {reason}")

        return val

    def _write(self, val: ValType) -> WriteRequest:
        write_request = WriteRequest(self, val)
        self._client._process_write_request(write_request)
        if not self._client._is_batch_write_in_progress():
            write_request.wait_for_completion()
        return write_request

    def unwatch(self) -> None:
        self._client.unwatch(self._display_path)

    def wait_update(self, timeout=3, previous_counter: Optional[int] = None) -> None:
        """Wait for the value to be updated by the server"""
        t = time.time()
        entry_counter = self._update_counter if previous_counter is None else previous_counter
        happened = False
        while time.time() - t < timeout:

            if self._status != ValueStatus.NeverSet and self._status != ValueStatus.Valid:
                if self._status == ValueStatus.ServerGone:
                    raise sdk_exceptions.InvalidValueError("Server has gone away")
                else:
                    raise RuntimeError("Unknown value status")

            if entry_counter != self._update_counter:
                happened = True
                break

            time.sleep(0.02)

        if not happened:
            raise sdk_exceptions.TimeoutException(f'Value of {self._shortname} did not update in {timeout}s')

    @property
    def value(self) -> ValType:
        """The last value received for this watchable"""
        return self._read()

    @value.setter
    def value(self, val: ValType) -> None:
        self._write(val)

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
        """Time of the last value update. Not reliable for change detection"""
        return self._last_value_dt

    @property
    def last_write_timestamp(self) -> Optional[datetime]:
        """Time of the last successful write operation."""
        return self._last_write_dt

    @property
    def datatype(self) -> EmbeddedDataType:
        """The data type of the device element pointed by this watchable"""
        return self._datatype

    @property
    def update_counter(self) -> int:
        """Number of value update gotten since creation of the handle. Can be safely used for change detection"""
        return self._update_counter
