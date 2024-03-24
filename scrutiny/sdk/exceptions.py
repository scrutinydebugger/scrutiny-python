#    exceptions.py
#        Definitions of all exceptions used across the Scrutiny SDK
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

class ScrutinySDKException(Exception):
    """Base class for all Scrutiny SDK exceptions"""
    pass


class ConnectionError(ScrutinySDKException):
    """Raised when a problem with the server communication occurs"""
    pass


class InvalidValueError(ScrutinySDKException):
    """Raised when trying to access a value that is unavailable"""
    pass


class OperationFailure(ScrutinySDKException):
    """Generic exception raised when a synchronous operation fails"""
    pass


class TimeoutException(ScrutinySDKException):
    """Raised when synchronous operations times out"""
    pass


class NameNotFoundError(ScrutinySDKException):
    """Raised when raised when trying to reference an element by its name and the name is invalid or unknown"""
    pass


class ApiError(ScrutinySDKException):
    """Base class for all error related to the API"""
    pass


class BadResponseError(ApiError):
    """Raised when the server API does not behave as expected. Rarely reaches the end user and often translate to an :class:`OperationFailure<OperationFailure>`"""
    pass


class ErrorResponseException(ApiError):
    """Raised when the server API actively reject a request. Rarely reaches the end user and often translate to an :class:`OperationFailure<OperationFailure>`"""
    pass
