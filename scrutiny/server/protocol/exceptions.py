#    exceptions.py
#        Some exceptions specific to the protocol
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

class InvalidRequestException(Exception):
    def __init__(self, req, *args, **kwargs):
        self.request = req
        super().__init__(*args, **kwargs)


class InvalidResponseException(Exception):
    def __init__(self, response, *args, **kwargs):
        self.response = response
        super().__init__(*args, **kwargs)
