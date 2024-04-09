#    text_stream_listener.py
#        Simple listener useful for debug. Prints all updates in a text stream
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
        """
        Create a listener that writes every value update it receive into a text stream,
        by formatting the update into a single-line string representation of the form:
        ``<time>ms\\t(<type>/<datatype>) <path>: <value>``.
         
        Where

        - <time> is the relative time in millisecond since the listener has been started
        - <type> is the watchable type : variable, alias or rpv
        - <datatype> is the value :class:`datatype<scrutiny.core.basic_types.EmbeddedDataType>`, such as : sint8, float32, uint16, etc.
        - <path> is the tree path used to identify the watchable at the server level    
        - <value> Value converted to text

        :param stream: The text stream to write to. Defaults to ``stdout``
        :param args: Passed to :class:`BaseListener<scrutiny.sdk.listeners.BaseListener>`
        :param kwargs: Passed to :class:`BaseListener<scrutiny.sdk.listeners.BaseListener>`
        """
        BaseListener.__init__(self, *args, **kwargs)
        self._stream = stream
        self._start_time = 0

    def setup(self) -> None:
        self._start_time = time.perf_counter()

    def receive(self, updates: List[ValueUpdate]) -> None:
        update_time = (time.perf_counter() - self._start_time)*1e3
        for update in updates:
            self._stream.write(f'{update_time:0.2f}ms\t ({update.watchable_type.name}/{update.datatype.name}) {update.display_path}: {update.value}\n')
    
    def teardown(self) -> None:
        self._stream.flush()
