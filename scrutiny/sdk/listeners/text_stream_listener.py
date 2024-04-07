from scrutiny.sdk.listeners import ValueUpdate
from . import BaseListener
import sys 
import time
from typing import List, TextIO, Any

class TextStreamListener(BaseListener):
    _stream:TextIO
    _start_time:float
    def __init__(self, stream:TextIO=sys.stdout, *args:Any, **kwargs:Any):
        BaseListener.__init__(self, *args, **kwargs)
        self._stream = stream
        self._start_time = 0

    def setup(self) -> None:
        self._start_time = time.perf_counter()

    def receive(self, updates: List[ValueUpdate]) -> None:
        update_time = time.perf_counter() - self._start_time
        for update in updates:
            self._stream.write(f'{update_time}\t{update.display_path}: {update.value}')
    
    def teardown(self) -> None:
        self._stream.flush()
