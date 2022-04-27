from typing import Literal


class GenericCallback:
    """
    This class is a way to workaround the limitation of mypy with assigning callbacks
    to Callable Types
    """

    def __init__(self, callback):
        self.callback = callback

    def __call__(self, *args, **kwargs):
        assert self.callback is not None
        self.callback(*args, **kwargs)


Endianness = Literal['little', 'big']
