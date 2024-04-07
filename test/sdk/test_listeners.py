from typing import List
import unittest

from scrutiny.core.basic_types import *
import scrutiny.sdk
sdk = scrutiny.sdk  # Workaround for vscode linter an submodule on alias
from datetime import datetime

from scrutiny.sdk.listeners import BaseListener, ValueUpdate
from scrutiny.sdk.listeners.buffered_reader_listener import BufferedReaderListener
from scrutiny.sdk.listeners.text_stream_listener import TextStreamListener
from test import ScrutinyUnitTest
from typing import *
import time
from scrutiny.sdk.watchable_handle import WatchableHandle, WatchableType
from scrutiny.sdk.client import ScrutinyClient
from io import StringIO

from test import logger

class WorkingTestListener(BaseListener):
    recv_list:List[ValueUpdate]
    setup_time:Optional[float]
    teardown_time:Optional[float]
    recv_time:Optional[float]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_time = None
        self.teardown_time = None
        self.recv_time = None
        self.recv_list = []
    
    def setup(self):
        self.setup_time = time.monotonic()
        time.sleep(0.2)
    
    def teardown(self):
        self.teardown_time = time.monotonic()

    def receive(self, updates: List[ValueUpdate]) -> None:
        self.recv_time=time.monotonic()
        self.recv_list.extend(updates)

class SetupFailedListener(BaseListener):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.teardown_called = False

    def setup(self):
        raise Exception("I failed!!")
    
    def teardown(self):
        self.teardown_called=True

    def receive(self, updates: List[ValueUpdate]) -> None:
        pass

class TeardownFailedListener(BaseListener):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_called = False

    def setup(self):
        self.setup_called = True
    
    def teardown(self):
        raise Exception("I failed!!")

    def receive(self, updates: List[ValueUpdate]) -> None:
        pass

class ReceiveFailedListener(BaseListener):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_called = False
        self.teardown_called = False

    def setup(self):
        self.setup_called = True
    
    def teardown(self):
        self.teardown_called = True

    def receive(self, updates: List[ValueUpdate]) -> None:
        raise Exception("I failed!!")

def wait_cond(cond, timeout, msg=""):
    timed_out = False
    t1 = time.monotonic()
    while True:
        if time.monotonic()-t1 > timeout:
            timed_out = True
            break
        if cond():
            break
        time.sleep(0.01)
    if timed_out:
        raise TimeoutError(msg)

class TestListeners(ScrutinyUnitTest):

    def setUp(self) -> None:
        dummy_client = ScrutinyClient()
        self.w1 = WatchableHandle(dummy_client, '/aaa/bbb/ccc')
        self.w2 = WatchableHandle(dummy_client, '/aaa/bbb/ccc2')
        self.w3 = WatchableHandle(dummy_client, '/aaa/bbb/ccc3')
        self.w4 = WatchableHandle(dummy_client, '/aaa/bbb/ccc4')

        self.w1._configure(watchable_type=WatchableType.Variable, datatype=EmbeddedDataType.float32, server_id='w1')
        self.w2._configure(watchable_type=WatchableType.Variable, datatype=EmbeddedDataType.sint32, server_id='w2')
        self.w3._configure(watchable_type=WatchableType.Alias, datatype=EmbeddedDataType.uint32, server_id='w3')
        self.w4._configure(watchable_type=WatchableType.RuntimePublishedValue, datatype=EmbeddedDataType.float64, server_id='w4')
    
    def test_listener_working_behavior(self):
        
        listener = WorkingTestListener()
        listener.subscribe([self.w1,self.w2,self.w4])  # w3 is not there on purpose

        with listener.start():
            self.assertTrue(listener.is_started)
            # Simulate the client
            self.w1._update_value(3.1415)
            self.w2._update_value(-1234)
            listener._broadcast_update([self.w1, self.w2])

            self.w3._update_value(0x12345678)
            self.w4._update_value(1.23456789)
            listener._broadcast_update([self.w3, self.w4])

            self.w1._update_value(-5.2)
            self.w3._update_value(0x12341234)
            listener._broadcast_update([self.w1, self.w3])

            self.w2._update_value(0x5555)
            self.w4._update_value(-9.999)
            listener._broadcast_update([self.w2, self.w4])
            
            expected_nb_element = 6
            def all_received():
                return listener.update_count >= expected_nb_element

            wait_cond(all_received, 1, f"Did not receive at least {expected_nb_element} updates")
        
        self.assertFalse(listener.is_started)
        self.assertEqual(len(listener.recv_list), expected_nb_element)
        self.assertEqual(listener.update_count, expected_nb_element)
        self.assertIsNotNone(listener.setup_time)
        self.assertIsNotNone(listener.recv_time)
        self.assertIsNotNone(listener.teardown_time)
        self.assertGreater(listener.recv_time, listener.setup_time )
        self.assertGreater(listener.teardown_time, listener.recv_time )

        self.assertEqual(listener.recv_list[0].display_path, self.w1.display_path)
        self.assertEqual(listener.recv_list[0].datatype, self.w1.datatype)
        self.assertIsInstance(listener.recv_list[0].update_timestamp, datetime)
        self.assertEqual(listener.recv_list[0].value, 3.1415)

        self.assertEqual(listener.recv_list[1].display_path, self.w2.display_path)
        self.assertEqual(listener.recv_list[1].datatype, self.w2.datatype)
        self.assertIsInstance(listener.recv_list[1].update_timestamp, datetime)
        self.assertEqual(listener.recv_list[1].value, -1234)

        self.assertEqual(listener.recv_list[2].display_path, self.w4.display_path)
        self.assertEqual(listener.recv_list[2].datatype, self.w4.datatype)
        self.assertIsInstance(listener.recv_list[2].update_timestamp, datetime)
        self.assertEqual(listener.recv_list[2].value, 1.23456789)

        self.assertEqual(listener.recv_list[3].display_path, self.w1.display_path)
        self.assertEqual(listener.recv_list[3].datatype, self.w1.datatype)
        self.assertIsInstance(listener.recv_list[3].update_timestamp, datetime)
        self.assertEqual(listener.recv_list[3].value, -5.2)

        self.assertEqual(listener.recv_list[4].display_path, self.w2.display_path)
        self.assertEqual(listener.recv_list[4].datatype, self.w2.datatype)
        self.assertIsInstance(listener.recv_list[4].update_timestamp, datetime)
        self.assertEqual(listener.recv_list[4].value, 0x5555)

        self.assertEqual(listener.recv_list[5].display_path, self.w4.display_path)
        self.assertEqual(listener.recv_list[5].datatype, self.w4.datatype)
        self.assertIsInstance(listener.recv_list[5].update_timestamp, datetime)
        self.assertEqual(listener.recv_list[5].value, -9.999)

        self.assertFalse(listener.error_occured)


    def test_listener_failing_setup(self):
        listener = SetupFailedListener()
        listener.subscribe([self.w1,self.w2,self.w4])  # w3 is not there on purpose

        with self.assertRaises(sdk.exceptions.OperationFailure):
            listener.start()

        self.assertFalse(listener.is_started)
        self.assertTrue(listener.teardown_called)
        self.assertTrue(listener.error_occured)
     
    def test_listener_failing_teardown(self):
        listener = TeardownFailedListener()
        listener.subscribe([self.w1,self.w2,self.w4])  # w3 is not there on purpose

        listener.start()
        self.assertTrue(listener.is_started)
        self.assertTrue(listener.setup_called)
        listener.stop() # Should not throw.
        self.assertFalse(listener.is_started)
        self.assertTrue(listener.error_occured)

    def test_listener_failing_receive(self):
        listener = ReceiveFailedListener()
        listener.subscribe([self.w1,self.w2,self.w4])  # w3 is not there on purpose

        listener.start()
        self.assertTrue(listener.is_started)
        self.assertTrue(listener.setup_called)

        self.w1._update_value(3.1415)
        self.w2._update_value(-1234)
        listener._broadcast_update([self.w1, self.w2])

        listener.stop() # Should not throw.
        self.assertFalse(listener.is_started)
        self.assertTrue(listener.error_occured)
     
    
    def test_queue_overflow_dropped(self):
        listener = WorkingTestListener(queue_max_size=1)
        listener.subscribe([self.w1])
        count = 100
        with listener.start():
            for i in range(count):
                self.w1._update_value(i)
                listener._broadcast_update([self.w1])
            
            def check_count():
                return listener.update_count + listener.drop_count >= count
            wait_cond(check_count, 0.5, f"Sum of dropped update + received update is not {count}")
            
        self.assertEqual(len(listener.recv_list), listener.update_count)
        self.assertLess(listener.update_count, count)
        self.assertGreater(listener.drop_count, 0)
        self.assertEqual(listener.update_count + listener.drop_count, count)


    def test_text_stream_listener(self):
        stream = StringIO()
        listener = TextStreamListener(stream)
        listener.subscribe([self.w1,self.w2, self.w3, self.w4])
        
        listener.start()
        count = 10
        for i in range(count):
            self.w1._update_value(i)
            self.w2._update_value(2*i)
            listener._broadcast_update([self.w1, self.w2])

        def all_received():
            return listener.update_count == 2*count
        
        wait_cond(all_received, 0.5, "Not all received in time")

        listener.stop() # Should not throw.
        
        lines = stream.getvalue().splitlines()
        for line in lines:
            logger.debug(f"\t {line}")
        self.assertEqual(len(lines), 2*count)
    
    def test_buffered_reader_listener(self):
        listener = BufferedReaderListener()
        listener.subscribe([self.w1,self.w2, self.w3, self.w4])
        
        listener.start()
        count = 10
        for i in range(count):
            self.w1._update_value(i)
            self.w2._update_value(2*i)
            listener._broadcast_update([self.w1, self.w2])

        def all_received():
            return listener.update_count == 2*count
        
        wait_cond(all_received, 0.5, "Not all received in time")

        listener.stop() 
        
        received = 0
        while not listener.get_queue().empty():
            listener.get_queue().get()
            received += 1
        self.assertEqual(received, 2*count)
    

if __name__ == '__main__':
    unittest.main()
