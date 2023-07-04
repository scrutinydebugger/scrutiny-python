
import threading
from datetime import datetime
import scrutiny.sdk.exceptions as sdk_exceptions

from typing import *

if TYPE_CHECKING:
    from scrutiny.sdk.watchable_handle import WatchableHandle


class WriteRequest:
    _value: Union[int, bool, float]
    _success: bool
    _completion_timestamp: Optional[datetime]
    _completed_event: threading.Event
    _watchable: "WatchableHandle"
    _failure_reason: str

    def __init__(self, watchable: "WatchableHandle", val: Union[int, bool, float]):
        self._value = val
        self._completed = False
        self._success = False
        self._completion_timestamp = None
        self._completed_event = threading.Event()
        self._watchable = watchable
        self._failure_reason = ""

    def _mark_complete(self, success: bool, failure_reason: str, timestamp: Optional[datetime] = None, ):
        self.success = success
        self._failure_reason = failure_reason
        if timestamp is None:
            self._completion_timestamp = datetime.now()
        else:
            self._completion_timestamp = timestamp
        self._completed = True
        self._completed_event.set()

    def wait_for_completion(self, timeout: float = 2):
        self._completed_event.wait(timeout=timeout)
        if not self._completed:
            raise sdk_exceptions.TimeoutException(f"Write did not complete. {self._watchable.display_path}")

        if not self._success:
            raise sdk_exceptions.OperationFailure(f"Write of {self._watchable.display_path} failed. {self._failure_reason}")

    @property
    def completed(self) -> bool:
        return self._completed_event.is_set()

    @property
    def is_success(self) -> bool:
        return self._success

    @property
    def completion_timestamp(self) -> Optional[datetime]:
        return self._completion_timestamp
