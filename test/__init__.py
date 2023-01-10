import logging
import unittest
from functools import wraps

__scrutiny__ = True  # we need something to know if we loaded scrutiny "test" module or something else (such as python "test" module)
logger = logging.getLogger('unittest')


class SkipOnException:
    def __init__(self, exception, msg=""):
        self.exception = exception
        self.msg = msg

    def __call__(self, f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except self.exception as e:
                raise unittest.SkipTest("%s. %s" % (self.msg, str(e)))
        return wrapper


class PrintableBytes(bytes):
    def __repr__(self) -> str:
        return 'bytes(' + self.hex() + ')'


class PrintableByteArray(bytearray):
    def __repr__(self) -> str:
        return 'bytearray(' + bytes(self).hex() + ')'


class ScrutinyUnitTest(unittest.TestCase):
    def assertEqual(self, v1, v2, *args, **kwargs):
        if isinstance(v1, bytes) and isinstance(v2, bytes):
            super().assertEqual(PrintableBytes(v1), PrintableBytes(v2), *args, **kwargs)
        elif isinstance(v1, bytearray) and isinstance(v2, bytearray):
            super().assertEqual(PrintableByteArray(v1), PrintableByteArray(v2), *args, **kwargs)
        else:
            super().assertEqual(v1, v2, *args, **kwargs)

    def assertNotEqual(self, v1, v2, *args, **kwargs):
        if isinstance(v1, bytes) and isinstance(v2, bytes):
            super().assertNotEqual(PrintableBytes(v1), PrintableBytes(v2), *args, **kwargs)
        elif isinstance(v1, bytearray) and isinstance(v2, bytearray):
            super().assertEqual(PrintableByteArray(v1), PrintableByteArray(v2), *args, **kwargs)
        else:
            super().assertNotEqual(v1, v2, *args, **kwargs)
