#    exceptions.py
#        Some exceptions specific to the protocol
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

class InvalidRequestException(Exception):
    """Raised when a bad request is received through the API"""

    def __init__(self, req, *args, **kwargs):
        self.request = req
        super().__init__(*args, **kwargs)


class InvalidResponseException(Exception):
    """Raised when a bad response is received from the device"""

    def __init__(self, response, *args, **kwargs):
        self.response = response
        super().__init__(*args, **kwargs)
