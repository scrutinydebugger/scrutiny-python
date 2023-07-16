#    exceptions.py
#        Definitions of all exceptions used across the Scrutiny SDK
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2023 Scrutiny Debugger

class ScrutinySDKException(Exception):
    pass


class ConnectionError(ScrutinySDKException):
    pass


class InvalidValueError(ScrutinySDKException):
    pass


class OperationFailure(ScrutinySDKException):
    pass


class TimeoutException(ScrutinySDKException):
    pass


class NameNotFoundError(ScrutinySDKException):
    pass


class ApiError(ScrutinySDKException):
    pass


class BadResponseError(ApiError):
    pass


class ErrorResponseException(ApiError):
    pass
