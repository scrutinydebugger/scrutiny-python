from typing import List, Optional
from scrutiny.server.device.links import rtt_link
from test import ScrutinyUnitTest
import time

class FakeRTTPort:
    data_written:bytearray
    data_to_read:bytearray

    write_chunk_size:int
    _opened:bool
    _connected:bool
    _target_connected:bool
    _tif:Optional[int]
    _target_device:Optional[str]

    def __init__(self, write_chunk_size:int=15) -> None:
        self.data_written = bytearray()
        self.data_to_read = bytearray()
        self.write_chunk_size = write_chunk_size
        self._opened = False 
        self._connected = False
        self._target_connected = False
        self._target_device = None

    def open(self) ->None:
        self._opened = True

    def opened(self) -> bool:
        return self._opened

    def close(self) -> None:
        self._opened = False
        self._connected = False
        self._target_connected = False

    def set_tif(self, val:int):
        self._tif = val

    def connect(self, device) -> None:
        self._target_device = device
        self._connected = True

    def connected(self) -> bool:
        return self._connected

    def target_connected(self) -> bool:
        return self._target_connected
    
    def rtt_write(self, buffer_index:int, data:bytes) -> int:
        chunked = data[0:self.write_chunk_size]
        self.data_written.extend(chunked)
        return len(chunked)

    def rtt_read(self, buffer_index:int, max_size:int) -> bytearray:
        read = self.data_to_read[0:max_size]
        self.data_to_read = self.data_to_read[len(read):]
        return read

    @property
    def product_name(self) -> str:
        return self.__class__.__name__
    
    def rtt_start(self, block_addr:Optional[int]) -> None:
        self._target_connected = True

class TestRTTLink(ScrutinyUnitTest):

    def setUp(self):
        self._old_port_func = rtt_link._get_jlink_class()
        rtt_link._set_jlink_class(FakeRTTPort)

    def wait_eq(self, func, val, timeout:float):
        t = time.perf_counter()
        while time.perf_counter() - t < timeout:
            if func() == val:
                break
        self.assertEqual(func(), val)
    
    def wait_true(self, func, timeout:float):
        self.wait_eq(func, True, timeout)
    
    def test_open_close(self):
        config = {
            'target_device' : "CORTEX-M0",
            'jlink_interface' : "SWD"
            }
        
        link = rtt_link.RttLink(config)
        link.initialize()
        self.assertTrue(link.operational())
        link.destroy()
        self.assertFalse(link.operational())

    def test_write_read(self):
        config = {
            'target_device' : "CORTEX-M0",
            'jlink_interface' : "SWD"
            }
        
        link = rtt_link.RttLink(config)
        link.initialize()
        self.assertIsNotNone(link.port)
        self.assertIsInstance(link.port, FakeRTTPort)
        assert isinstance(link.port, FakeRTTPort)   # mypy
        
        link.port.data_to_read.extend(b'abcdef')
        data = link.read(timeout=1)
        self.assertIsNotNone(data)
        self.assertEqual(data, b'abcdef')
        self.assertEqual(len(link.port.data_to_read), 0)

        payload = b'abcdefghijk'
        link.port.write_chunk_size = 5   # Emulate internal buffer size
        link.write(payload)
        self.wait_true(lambda: len(link.port.data_written) == len(payload), 1)
        self.assertEqual(bytes(link.port.data_written), payload)

    def test_error_on_bad_interface(self):
        with self.assertRaises(Exception):
            rtt_link.RttLink({
                'target_device' : "CORTEX-M0",
                'jlink_interface' : "idontexist"
            })


    def tearDown(self) -> None:
        rtt_link._set_jlink_class(self._old_port_func)
        return super().tearDown()
        
