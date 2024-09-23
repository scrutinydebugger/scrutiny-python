__all__ = ['StreamMaker', 'StreamParser']

from typing import Optional, Any
from hashlib import sha1
import queue
import re
import logging
import time

HASH_SIZE = 20
HASH_ALGO = sha1

class StreamMaker:
    @classmethod
    def encode(self, data:Any):
        datasize = len(data)
        if datasize > 2**32-1:
            raise RuntimeError("Message too big")
        hasher = HASH_ALGO(data)
        out = bytearray()
        out.extend(f"<SCRUTINY size={datasize:08x}>".encode('utf8'))
        out.extend(data)
        out.extend(hasher.digest())
        return out


class StreamParser:
    MAX_HEADER_LENGTH = len("<SCRUTINY size=00000000>")

    _data_length:Optional[int]
    _bytes_read:int
    _buffer:bytearray
    _remainder:bytearray
    _msg_queue:"queue.Queue[bytes]"
    _pattern:re.Pattern
    _logger:logging.Logger
    _last_chunk_timestamp:float
    _interchunk_timeout:float

    def __init__(self, interchunk_timeout:Optional[float]=None):
        self._data_length = None
        self._buffer = bytearray()
        self._msg_queue = queue.Queue()
        self._pattern = re.compile(b"<SCRUTINY size=([a-fA-F0-9]+)>")
        self._logger = logging.getLogger(self.__class__.__name__)
        self._last_chunk_timestamp = time.monotonic()
        self._interchunk_timeout = interchunk_timeout

    def parse(self, chunk):
        done = False
        if self._data_length is not None and self._interchunk_timeout is not None:
            if time.monotonic() - self._last_chunk_timestamp > self._interchunk_timeout:
                self.reset()

        self._buffer.extend(chunk)
        while not done:
            if self._data_length is None:
                m = self._pattern.search(self._buffer)
                if m:
                    try:
                        self._data_length = int(m.groups(1)[0], 16)
                    except Exception:
                        self.data_length = None
                        self._logger.error("Received an unparsable message length")
                        done = True
                    
                    if self._data_length:
                        self._data_length += HASH_SIZE
                    self._buffer = self._buffer[m.end():]   # Drop header
                else:
                    self._buffer = self._buffer[-self.MAX_HEADER_LENGTH:]   # Drop grabage
                    done = True
                
            if self._data_length is not None:                
                if len(self._buffer) >= self._data_length:
                    try:
                        end_of_data = self._data_length-HASH_SIZE
                        thehash = self._buffer[end_of_data:self._data_length]
                        if thehash == HASH_ALGO(self._buffer[0:end_of_data]).digest():
                            self._msg_queue.put(bytes(self._buffer[0:end_of_data]))
                        else:
                            self._logger.error("Bad hash. Dropping datagram")
                    except queue.Full:
                        self._logger.error("Receive queue full. Dropping datagram")
                    finally:
                        self._buffer = self._buffer[self._data_length:]   # remainder
                        self._data_length = None    # Indicates we are not reading a datagram
                else:
                    done=True
                        
        self._last_chunk_timestamp = time.monotonic()
    
    def queue(self) -> "queue.Queue[bytes]":
        return self._msg_queue

    def reset(self) -> None:
        self._data_length = None
        self._buffer.clear()
