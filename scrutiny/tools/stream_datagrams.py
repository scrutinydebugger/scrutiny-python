__all__ = ['StreamMaker', 'StreamParser']

from typing import Optional, Any, Iterable, SupportsIndex, cast
from hashlib import md5
import queue
import re
import logging
import time

HASH_SIZE = 16
HASH_FUNC = md5 # Fastest 128bits+
MAX_MTU=2**32-1
MAX_HEADER_LENGTH = len("<SCRUTINY size=00000000>")

class StreamMaker:
    _use_hash:bool
    _mtu:int

    def __init__(self, mtu:int, use_hash:bool=True) -> None:
        self._use_hash = use_hash
        if mtu > MAX_MTU:
            raise ValueError(f"MTU is too big. Max={MAX_MTU}")
        self._mtu = mtu

    def encode(self, data:Any) -> bytearray:
        datasize = len(data)
        if datasize > self._mtu:
            raise RuntimeError(f"Message too big. MTU={self._mtu}")
        out = bytearray()
        out.extend(f"<SCRUTINY size={datasize:x}>".encode('utf8'))
        out.extend(data)
        if self._use_hash:
            out.extend(HASH_FUNC(data).digest())
        return out


class StreamParser:
    _data_length:Optional[int]
    _bytes_read:int
    _buffer:bytearray
    _remainder:bytearray
    _msg_queue:"queue.Queue[bytes]"
    _pattern:re.Pattern[bytes]
    _logger:logging.Logger
    _last_chunk_timestamp:float
    _interchunk_timeout:Optional[float]
    _use_hash:bool
    _mtu:int

    def __init__(self, mtu:int, interchunk_timeout:Optional[float]=None, use_hash:bool=True):
        if mtu > MAX_MTU:
            raise ValueError(f"MTU is too big. Max={MAX_MTU}")
        
        self._data_length = None
        self._buffer = bytearray()
        self._msg_queue = queue.Queue()
        self._pattern = re.compile(b"<SCRUTINY size=([a-fA-F0-9]+)>")
        self._logger = logging.getLogger(self.__class__.__name__)
        self._last_chunk_timestamp = time.monotonic()
        self._interchunk_timeout = interchunk_timeout
        self._use_hash = use_hash
        self._mtu = mtu

    def parse(self, chunk:Iterable[SupportsIndex]) -> None:
        done = False
        if self._data_length is not None and self._interchunk_timeout is not None:
            if time.monotonic() - self._last_chunk_timestamp > self._interchunk_timeout:
                self.reset()

        self._buffer.extend(chunk)
        while not done:
            if self._data_length is None:   # We are waiting for a header
                m = self._pattern.search(self._buffer)
                if m:   # We found a header
                    try:
                        capture = cast(bytes,  m.groups(1)[0])
                        self._data_length = int(capture.decode('utf8'), 16) # Read the data length (excluding the hash)
                    except Exception:
                        self._data_length = None
                        self._logger.error("Received an unparsable message length")
                        done = True

                    if self._data_length:
                        if self._data_length > self._mtu:
                            self._logger.error(f"Received a message with length={self._data_length} which is bigger than the MTU ({self._mtu})")
                            self._data_length = None     #  Do not go in reception mode. Leave subsequent data be sonsidered as garbage until the next header
                        elif self._use_hash:
                            self._data_length += HASH_SIZE
                    self._buffer = self._buffer[m.end():]   # Drop header and previous garbage
                else:
                    self._buffer = self._buffer[-MAX_HEADER_LENGTH:]   # Drop grabage
                    done = True
            
            if self._data_length is not None: # Header is received already, we read successive data
                if len(self._buffer) >= self._data_length:  # Message is complete
                    try:
                        # Make a copy of the message in the output queue and remove it from the work buffer
                        end_of_data = self._data_length
                        if self._use_hash:
                            end_of_data -= HASH_SIZE
                            thehash = self._buffer[end_of_data:self._data_length]
                            if thehash == HASH_FUNC(self._buffer[0:end_of_data]).digest():
                                self._msg_queue.put(bytes(self._buffer[0:end_of_data]))
                            else:
                                self._logger.error("Bad hash. Dropping datagram")   # Dropped in "finally" block
                        else:
                            self._msg_queue.put(bytes(self._buffer[0:end_of_data]))
                    except queue.Full:
                        self._logger.error("Receive queue full. Dropping datagram")
                    finally:
                        # Remove the message, keeps the remainder. We may have the start of another message
                        self._buffer = self._buffer[self._data_length:]   
                        self._data_length = None    # Indicates we are not reading a datagram
                else:
                    # We have no more data to process, wait next chunk
                    done=True
                        
        self._last_chunk_timestamp = time.monotonic()
    
    def queue(self) -> "queue.Queue[bytes]":
        return self._msg_queue

    def reset(self) -> None:
        self._data_length = None
        self._buffer.clear()
