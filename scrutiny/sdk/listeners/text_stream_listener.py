#    text_stream_listener.py
#        Simple listener usable for debug. Prints all update in a text stream
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['TextStreamListener']
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
        update_time = (time.perf_counter() - self._start_time)*1e3
        for update in updates:
            self._stream.write(f'{update_time:0.2f}ms\t ({update.watchable_type.name} - {update.datatype.name}) {update.display_path}: {update.value}\n')
    
    def teardown(self) -> None:
        self._stream.flush()
