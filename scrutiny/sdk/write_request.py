
import threading
from datetime import datetime
import scrutiny.sdk as sdk

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

    def _mark_complete(self, success: bool, failure_reason: str = "", timestamp: Optional[datetime] = None, ):
        self._success = success
        self._failure_reason = failure_reason
        if timestamp is None:
            self._completion_timestamp = datetime.now()
        else:
            self._completion_timestamp = timestamp
        self._completed = True
        self._completed_event.set()

    def wait_for_completion(self, timeout: float = 2):
        """Wait for the write request to get completed. 

        :raises sdk.TimeoutException: If the request does not complete within the allowed time
        :raises sdk.OperationFailure: If the request complete with a failure state
        """
        self._completed_event.wait(timeout=timeout)
        if not self._completed:
            raise sdk.exceptions.TimeoutException(f"Write did not complete. {self._watchable.display_path}")

        if not self._success:
            raise sdk.exceptions.OperationFailure(f"Write of {self._watchable.display_path} failed. {self._failure_reason}")

    @property
    def completed(self) -> bool:
        """Indicates whether the write request has completed or not"""
        return self._completed_event.is_set()

    @property
    def is_success(self) -> bool:
        """Indicates whether the write request has successfully completed or not"""
        return self._success

    @property
    def completion_timestamp(self) -> Optional[datetime]:
        """The time at which the write request has been completed. None if not completed yet"""
        return self._completion_timestamp

    @property
    def failure_reason(self) -> str:
        """When the write request failed, this property contains the reason for the failure. Empty string if not completed or succeeded"""
        return self._failure_reason

    @property
    def watchable(self) -> "WatchableHandle":
        """A reference to the watchable handle that is being written by this write request"""
        return self._watchable