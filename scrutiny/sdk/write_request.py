#    write_request.py
#        A object representing a request to write a watchable element.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2023 Scrutiny Debugger

__all__ = ['WriteRequest']

from scrutiny.sdk.pending_request import PendingRequest
from scrutiny.tools.typing import *

if TYPE_CHECKING:
    from scrutiny.sdk.watchable_handle import WatchableHandle


class WriteRequest(PendingRequest):
    """A handle to a write request. Reports the progress and the status of the request. 
    Gets updated by the client thread"""
    _value: Union[int, bool, float, str]  # Value to be written
    _watchable: "WatchableHandle"       # Watchable targeted by this update request

    def __init__(self, watchable: "WatchableHandle", val: Union[int, bool, float, str]) -> None:
        super().__init__(watchable._client)

        self._value = val
        self._watchable = watchable

    def _timeout_exception_msg(self, timeout: float) -> str:
        return f"Write did not complete in {timeout} seconds. {self._watchable.display_path}"

    def _failure_exception_msg(self) -> str:
        return f"Write of {self._watchable.display_path} failed. {self._failure_reason}"

    @property
    def watchable(self) -> "WatchableHandle":
        """A reference to the watchable handle that is being written by this write request"""
        return self._watchable
