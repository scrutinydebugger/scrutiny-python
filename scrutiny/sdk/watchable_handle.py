
import queue
import threading
from datetime import datetime
import time
import enum

from scrutiny.sdk.definitions import *
from scrutiny.core.basic_types import *
import scrutiny.sdk.exceptions as sdk_exceptions
from scrutiny.sdk._write_request import WriteRequest
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
    _last_value_update: Optional[datetime]
    _write_queue: "queue.Queue[WriteRequest]"

    def __init__(self, client: "ScrutinyClient", display_path: str):
        self._client = client
        self._display_path = display_path
        self._shortname = display_path.split('/')[-1]
        self._lock = threading.Lock()
        self._set_invalid(ValueStatus.NeverSet)

    def __repr__(self):
        addr = "0x%0.8x" % id(self)
        return f'<{self.__class__.__name__} "{self._shortname}" [{self._datatype.name}] at {addr}>'

    def _configure(self, watchable_type: WatchableType, datatype: EmbeddedDataType, server_id: str) -> None:
        self._lock.acquire()
        self._watchable_type = watchable_type
        self._datatype = datatype
        self._server_id = server_id
        self._status = ValueStatus.NeverSet
        self._value = None
        self._last_value_update = None
        self._lock.release()

    def _update_value(self, val: ValType) -> None:
        self._lock.acquire()
        if self._status != ValueStatus.ServerGone:
            self._status = ValueStatus.Valid
            self._value = val
            self._last_value_update = datetime.now()
        else:
            self._value = None
        self._lock.release()

    def _set_invalid(self, status: ValueStatus):
        assert status != ValueStatus.Valid

        self._lock.acquire()
        self._value = None
        self._status = status
        self._server_id = None
        self._watchable_type = WatchableType.NA
        self._datatype = EmbeddedDataType.NA
        self._lock.release()

    def wait_update(self, timeout=3, since_timestamp: Optional[datetime] = None) -> None:
        t = time.time()
        entry_timestamp = self._last_value_update if since_timestamp is None else since_timestamp
        happened = False
        while time.time() - t < timeout:

            if self._status != ValueStatus.NeverSet and self._status != ValueStatus.Valid:
                if self._status == ValueStatus.ServerGone:
                    raise sdk_exceptions.InvalidValueError("Server has gone away")
                else:
                    raise RuntimeError("Unknown value status")

            if entry_timestamp != self._last_value_update:
                happened = True
                break

            time.sleep(0.02)

        if not happened:
            raise sdk_exceptions.TimeoutException(f'Value of {self._shortname} did not update in {timeout}s')

    def _read(self) -> ValType:
        self._lock.acquire()
        val = self._value
        val_status = self._status
        self._lock.release()

        if val is None or val_status != ValueStatus.Valid:
            if val_status == ValueStatus.NeverSet:
                reason = 'Never set'
            elif val_status == ValueStatus.ServerGone:
                reason = "Server has gone away"
            else:
                raise RuntimeError(f"Unknown value status {val_status}")
            raise sdk_exceptions.InvalidValueError(f"Value of {self._shortname} is unusable. {reason}")

        return val

    @property
    def value(self) -> ValType:
        return self._read()

    @value.setter
    def value(self, val: ValType) -> None:
        write_request = self._write(val)
        write_request.wait_for_completion()

    def _write(self, val: ValType) -> WriteRequest:
        write_request = WriteRequest(self, val)
        self._write_queue.put(write_request)
        return write_request

    @property
    def display_path(self) -> str:
        return self._display_path

    @property
    def name(self) -> str:
        return self._shortname

    @property
    def get_type(self) -> WatchableType:
        return self._watchable_type

    @property
    def value_bool(self) -> bool:
        return bool(self.value)

    @property
    def value_int(self) -> int:
        return int(self.value)

    @property
    def value_float(self) -> float:
        return float(self.value)

    @property
    def last_update_timestamp(self) -> Optional[datetime]:
        return self._last_value_update
