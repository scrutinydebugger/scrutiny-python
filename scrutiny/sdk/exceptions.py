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
