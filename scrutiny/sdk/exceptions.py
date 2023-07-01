__all__ = [
    'ScrutinySDKException',
    'ConnectionError'
]


class ScrutinySDKException(Exception):
    pass


class ConnectionError(ScrutinySDKException):
    pass
