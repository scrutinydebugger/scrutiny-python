#    pending_request.py
#        A base class for Future objects given to the suer
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

__all__ = ['PendingRequest']

from datetime import datetime
import threading
import time

from scrutiny.tools import validation
from scrutiny import sdk

from scrutiny.tools.typing import *
if TYPE_CHECKING:
    from scrutiny.sdk.client import ScrutinyClient


class PendingRequest:
    _client: "ScrutinyClient"

    _success: bool  # If the request has been successfully completed
    _completion_datetime: Optional[datetime]   # datetime of the completion. None if incomplete
    _completed_event: threading.Event   # Event that gets set upon completion of the request
    _failure_reason: str    # Textual description of the reason of the failure to complete. Empty string if incomplete or succeeded
    _monotonic_creation_timestamp: float

    def __init__(self, client: "ScrutinyClient") -> None:
        self._client = client
        self._completed = False
        self._success = False
        self._completion_datetime = None
        self._completed_event = threading.Event()
        self._failure_reason = ""
        self._monotonic_creation_timestamp = time.monotonic()

    def _is_expired(self, timeout: float) -> bool:
        return time.monotonic() - self._monotonic_creation_timestamp > timeout

    def _mark_complete(self, success: bool, failure_reason: str = "", server_time_us: Optional[float] = None) -> None:
        # Put a request in "completed" state. Expected to be called by the client worker thread
        self._success = success
        self._failure_reason = failure_reason
        if server_time_us is None:
            self._completion_datetime = datetime.now()
        else:
            self._completion_datetime = self._client._server_timebase.micro_to_dt(server_time_us)
        self._completed = True
        self._completed_event.set()

    def _timeout_exception_msg(self, timeout: float) -> str:
        return f"Request did not complete in {timeout} seconds"

    def _failure_exception_msg(self) -> str:
        return f"Request failed to complete. {self._failure_reason}"

    def wait_for_completion(self, timeout: Optional[float] = None) -> None:
        """Wait for the request to complete

        :params timeout: Maximum wait time in seconds. Waits forever if ``None``

        :raise TimeoutException: If the request does not complete in less than the specified timeout value
        :raise OperationFailure: If an error happened that prevented the request to successfully complete
        """
        timeout = validation.assert_float_range_if_not_none(timeout, 'timeout', minval=0)
        self._completed_event.wait(timeout=timeout)
        if not self._completed:
            assert timeout is not None
            raise sdk.exceptions.TimeoutException(self._timeout_exception_msg(timeout))
        assert self._completed_event.is_set()

        if not self._success:
            raise sdk.exceptions.OperationFailure(self._failure_exception_msg())

    @property
    def completed(self) -> bool:
        """Indicates whether the request has completed or not"""
        return self._completed_event.is_set()

    @property
    def is_success(self) -> bool:
        """Indicates whether the request has successfully completed or not"""
        return self._success

    @property
    def completion_datetime(self) -> Optional[datetime]:
        """The time at which the request has been completed. ``None`` if not completed yet"""
        return self._completion_datetime

    @property
    def failure_reason(self) -> str:
        """When the request failed, this property contains the reason for the failure. Empty string if not completed or succeeded"""
        return self._failure_reason
