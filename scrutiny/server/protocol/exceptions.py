#    exceptions.py
#        Some exceptions specific to the protocol
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from typing import Any

class InvalidRequestException(Exception):
    """Raised when a bad request is received through the API"""
    request:Any
    def __init__(self, req:Any, *args:Any, **kwargs:Any) -> None:
        self.request = req
        super().__init__(*args, **kwargs)


class InvalidResponseException(Exception):
    """Raised when a bad response is received from the device"""
    response:Any
    def __init__(self, response:Any, *args:Any, **kwargs:Any) -> None:
        self.response = response
        super().__init__(*args, **kwargs)
