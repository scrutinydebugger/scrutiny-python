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
