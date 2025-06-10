#    stream_datagrams.py
#        Internal tool to transmit datagrams over a stream. Used by the server and the clients
#        to exchange JSON objects over TCP
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

__all__ = ['StreamMaker', 'StreamParser']

from dataclasses import dataclass
from hashlib import md5
import queue
import re
import logging
import time
import zlib

from scrutiny.tools.typing import *

HASH_SIZE = 16
HASH_FUNC = md5  # Fastest 128bits+
MAX_MTU = 2**32 - 1
DEFAULT_COMPRESS = True
COMPRESSION_LEVEL = 1
MAX_HEADER_LENGTH = len("<SCRUTINY size=00000000 flags=ch>")


class StreamMaker:
    """Tool that encapsulate a chunk of data in a sized datagram with a header that can be sent onto a stream for reconstruction"""
    _use_hash: bool
    _mtu: int
    _compress: bool
    _flags: str

    def __init__(self, mtu: int, use_hash: bool = True, compress: bool = DEFAULT_COMPRESS) -> None:
        self._use_hash = use_hash
        self._compress = compress
        if mtu > MAX_MTU:
            raise ValueError(f"MTU is too big. Max={MAX_MTU}")
        self._mtu = mtu
        self._flags = ""
        if self._compress:
            self._flags += 'c'
        if self._use_hash:
            self._flags += 'h'

    def encode(self, data: Any) -> bytearray:
        if self._compress:
            data = zlib.compress(data, level=COMPRESSION_LEVEL)
        datasize = len(data)
        if datasize > self._mtu:
            raise RuntimeError(f"Message too big. MTU={self._mtu}")
        out = bytearray()
        out.extend(f"<SCRUTINY size={datasize:x} flags={self._flags}>".encode('utf8'))
        out.extend(data)
        if self._use_hash:
            out.extend(HASH_FUNC(data).digest())
        return out


@dataclass
class PayloadProperties:
    __slots__ = ('data_length', 'compressed', 'use_hash')

    data_length: int
    compressed: bool
    use_hash: bool


class StreamParser:
    """A parser that reads a stream and extracts datagrams """
    _payload_properties: Optional[PayloadProperties]
    _bytes_read: int
    _buffer: bytearray
    _remainder: bytearray
    _msg_queue: "queue.Queue[bytes]"
    _pattern: "re.Pattern[bytes]"
    _logger: logging.Logger
    _last_chunk_timestamp: float
    _interchunk_timeout: Optional[float]
    _mtu: int

    def __init__(self, mtu: int, interchunk_timeout: Optional[float] = None):
        if mtu > MAX_MTU:
            raise ValueError(f"MTU is too big. Max={MAX_MTU}")

        self._payload_properties = None
        self._buffer = bytearray()
        self._msg_queue = queue.Queue(maxsize=100)
        self._pattern = re.compile(b"<SCRUTINY size=([a-fA-F0-9]+) flags=(c?h?)>")
        self._logger = logging.getLogger(self.__class__.__name__)
        self._last_chunk_timestamp = time.perf_counter()
        self._interchunk_timeout = interchunk_timeout
        self._mtu = mtu

    def parse(self, chunk: Union[bytes, bytearray]) -> None:
        done = False
        if self._payload_properties is not None and self._interchunk_timeout is not None:
            if time.perf_counter() - self._last_chunk_timestamp > self._interchunk_timeout:
                self.reset()

        self._buffer.extend(chunk)
        while not done:
            if self._payload_properties is None:   # We are waiting for a header
                m = self._pattern.search(self._buffer)
                if m:   # We found a header
                    try:
                        size_capture = cast(bytes, m.group(1))
                        flags_capture = cast(bytes, m.group(2))
                        self._payload_properties = PayloadProperties(
                            data_length=int(size_capture.decode('utf8'), 16),  # Read the data length (excluding the hash)
                            use_hash=b'h' in flags_capture,
                            compressed=b'c' in flags_capture
                        )

                    except Exception:
                        self._payload_properties = None
                        self._logger.error("Received an unparsable message length")
                        done = True

                    if self._payload_properties is not None:
                        if self._payload_properties.data_length > self._mtu:
                            self._logger.error(
                                f"Received a message with length={self._payload_properties.data_length} which is bigger than the MTU ({self._mtu})")
                            self._payload_properties = None  # Do not go in reception mode. Leave subsequent data be considered as garbage until the next header
                        elif self._payload_properties.use_hash:
                            self._payload_properties.data_length += HASH_SIZE
                    self._buffer = self._buffer[m.end():]   # Drop header and previous garbage
                else:
                    self._buffer = self._buffer[-MAX_HEADER_LENGTH:]   # Drop garbage
                    done = True

            if self._payload_properties is not None:  # Header is received already, we read successive data
                if len(self._buffer) >= self._payload_properties.data_length:  # Message is complete
                    try:
                        # Make a copy of the message in the output queue and remove it from the work buffer
                        end_of_data = self._payload_properties.data_length
                        if self._payload_properties.use_hash:
                            end_of_data -= HASH_SIZE
                            thehash = self._buffer[end_of_data:self._payload_properties.data_length]
                            if thehash == HASH_FUNC(self._buffer[0:end_of_data]).digest():
                                self._receive_data(bytes(self._buffer[0:end_of_data]), self._payload_properties.compressed)
                            else:
                                self._logger.error("Bad hash. Dropping datagram")   # Dropped in "finally" block
                        else:
                            self._receive_data(bytes(self._buffer[0:end_of_data]), self._payload_properties.compressed)
                    finally:
                        # Remove the message, keeps the remainder. We may have the start of another message
                        self._buffer = self._buffer[self._payload_properties.data_length:]
                        self._payload_properties = None    # Indicates we are not reading a datagram
                else:
                    # We have no more data to process, wait next chunk
                    done = True

        self._last_chunk_timestamp = time.perf_counter()

    def _receive_data(self, data: bytes, compressed: bool) -> None:
        try:
            if compressed:
                data = zlib.decompress(data)
            self._msg_queue.put_nowait(data)
        except zlib.error:
            self._logger.error("Failed to decompress received data. Is the sender using compression?")
        except queue.Full:
            self._logger.error("Receive queue full. Dropping datagram")

    def queue(self) -> "queue.Queue[bytes]":
        return self._msg_queue

    def reset(self) -> None:
        self._data_length = None
        self._buffer.clear()
