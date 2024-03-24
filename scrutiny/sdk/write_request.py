#    write_request.py
#        A object representing a request to write a watchable element.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import threading
from datetime import datetime
import scrutiny.sdk as sdk

from typing import Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from scrutiny.sdk.watchable_handle import WatchableHandle


class WriteRequest:
    """A handle to a write request. Reports the progress and the status of the request. 
    Gets updated by the client thread"""
    _value: Union[int, bool, float]  # Value to be written
    _success: bool  # If the request has been successfully completed
    _completed: bool    # Indicates if the write request has been processed (regardless of success state)
    _completion_datetime: Optional[datetime]   # datetime of the completion. None if incomplete
    _completed_event: threading.Event   # Event that gets set upon completion of the request
    _watchable: "WatchableHandle"       # Watchable targeted by this update request
    _failure_reason: str    # Textual description of the reason of the failure to complete. Empty string if incomplete or succeeded

    def __init__(self, watchable: "WatchableHandle", val: Union[int, bool, float]) -> None:
        self._value = val
        self._completed = False
        self._success = False
        self._completion_datetime = None
        self._completed_event = threading.Event()
        self._watchable = watchable
        self._failure_reason = ""

    def _mark_complete(self, success: bool, failure_reason: str = "", timestamp: Optional[datetime] = None) -> None:
        # Put a request in "completed" state. Expected to be called by the client worker thread
        self._success = success
        self._failure_reason = failure_reason
        if timestamp is None:
            self._completion_datetime = datetime.now()
        else:
            self._completion_datetime = timestamp
        self._completed = True
        self._completed_event.set()

    def wait_for_completion(self, timeout: float = 5) -> None:
        """Wait for the write request to get completed. 

        :raise TimeoutException: If the request does not complete within the allowed time
        :raise OperationFailure: If the request complete with a failure state
        """
        self._completed_event.wait(timeout=timeout)
        if not self._completed:
            raise sdk.exceptions.OperationFailure(f"Write did not complete. {self._watchable.display_path}")

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
    def completion_datetime(self) -> Optional[datetime]:
        """The time at which the write request has been completed. None if not completed yet"""
        return self._completion_datetime

    @property
    def failure_reason(self) -> str:
        """When the write request failed, this property contains the reason for the failure. Empty string if not completed or succeeded"""
        return self._failure_reason

    @property
    def watchable(self) -> "WatchableHandle":
        """A reference to the watchable handle that is being written by this write request"""
        return self._watchable
