#    test_listeners.py
#        Test suite for the SDK listener feature
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from typing import List
import unittest

from scrutiny.core.basic_types import *
import scrutiny.sdk
sdk = scrutiny.sdk  # Workaround for vscode linter an submodule on alias
from datetime import datetime

from scrutiny.sdk.listeners import BaseListener, ValueUpdate
from scrutiny.sdk.listeners.buffered_reader_listener import BufferedReaderListener
from scrutiny.sdk.listeners.text_stream_listener import TextStreamListener
from scrutiny.sdk.listeners.csv_file_listener import CSVConfig, CSVFileListener
from test import ScrutinyUnitTest
from typing import *
import time
from scrutiny.sdk.watchable_handle import WatchableHandle, WatchableType
from scrutiny.sdk.client import ScrutinyClient
from io import StringIO
from tempfile import TemporaryDirectory
import os
import csv

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
        self.w5 = WatchableHandle(dummy_client, '/aaa/bbb/ccc5')

        self.w1._configure(watchable_type=WatchableType.Variable, datatype=EmbeddedDataType.float32, server_id='w1')
        self.w2._configure(watchable_type=WatchableType.Variable, datatype=EmbeddedDataType.sint32, server_id='w2')
        self.w3._configure(watchable_type=WatchableType.Alias, datatype=EmbeddedDataType.uint32, server_id='w3')
        self.w4._configure(watchable_type=WatchableType.RuntimePublishedValue, datatype=EmbeddedDataType.float64, server_id='w4')
        self.w5._configure(watchable_type=WatchableType.RuntimePublishedValue, datatype=EmbeddedDataType.boolean, server_id='w5')
    
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
        listener.subscribe([self.w1, self.w2, self.w3, self.w4])
        
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
    
    def test_csv_writer_listener_no_limits(self):
        with TemporaryDirectory() as tempdir:
            csv_config = CSVConfig()
            listener = CSVFileListener(
                folder=tempdir,
                filename='my_file',
                lines_per_file=None,
                datetime_format=r'%Y-%m-%d %H:%M:%S',
                csv_config=csv_config
            )
            listener.subscribe([self.w1,self.w2, self.w3, self.w4, self.w5])
            
            with listener.start():
                count = 10
                for i in range(count):
                    self.w1._update_value(i*1.1)
                    self.w2._update_value(-2*i)
                    self.w3._update_value(3*i)
                    self.w5._update_value(i%2==0)
                    if i == 6:
                        to_update=[self.w1, self.w5, self.w2]           # Puposely out of order
                    else:
                        to_update=[self.w1, self.w2, self.w5, self.w3]  # Puposely out of order
                        if i > 0:
                            self.w4._update_value(4.4123*i)
                            to_update.append(self.w4)
                    
                    listener._broadcast_update(to_update)

                def all_received():
                    return listener.update_count == 5*count-1-2 # Remove 1 for index 0 + 2 for index 6
                
                wait_cond(all_received, 0.5, "Not all received in time")
                 


            self.assertTrue(os.path.exists(os.path.join(tempdir, 'my_file.csv' )))
            f = open(os.path.join(tempdir, 'my_file.csv' ), 'r', encoding=csv_config.encoding, newline=csv_config.newline)
            reader = csv.reader(f, delimiter=csv_config.delimiter, quotechar=csv_config.quotechar, quoting=csv_config.quoting)
            rows = iter(reader)
            headers = next(rows)
            self.assertEqual(headers[0], 'datetime' )
            self.assertEqual(headers[1], 'time (ms)' )
            self.assertEqual(headers[-1], 'update flags' )
            all_watchables = sorted([self.w1, self.w2, self.w3, self.w4, self.w5], key=lambda x: x.display_path)
            index=2
            for watchable in all_watchables:
                self.assertEqual(headers[index], watchable.display_path )
                index+=1
            
            all_rows = list(rows)
            self.assertEqual(len(all_rows), 10)
            for i in range(len(all_rows)):
                row = all_rows[i]
                datetime.strptime(row[0], r'%Y-%m-%d %H:%M:%S')    # check it can be parsed
                float(row[1])  # ensure it can be parsed

                if i == 0:
                    self.assertEqual(row[-1], '1,1,1,0,1')
                elif i==6:
                    self.assertEqual(row[-1], '1,1,0,0,1')
                else:
                    self.assertEqual(row[-1], '1,1,1,1,1')


                for col in range(2, len(headers)-1):
                    if headers[col] == self.w1.display_path:
                        self.assertEqual(row[col], i*1.1)
                    elif headers[col] == self.w2.display_path:
                        self.assertEqual(row[col], -2*i)
                    elif headers[col] == self.w3.display_path:
                        if i == 6:
                            self.assertEqual(row[col], 3*(i-1))
                        else:
                            self.assertEqual(row[col], 3*i)
                    elif headers[col] == self.w4.display_path:
                        if i == 0:
                            self.assertEqual(row[col], '')
                        elif i == 6:
                            self.assertEqual(row[col], (i-1)*4.4123)
                        else:
                            self.assertEqual(row[col], i*4.4123)
                    elif headers[col] == self.w5.display_path:
                        self.assertEqual(row[col], 1 if i%2==0 else 0)


    def test_csv_writer_listener_file_split(self):
        with TemporaryDirectory() as tempdir:
            csv_config = CSVConfig()
            listener = CSVFileListener(
                folder=tempdir,
                filename='my_file',
                lines_per_file=100,
                file_part_0pad=4,
                datetime_format=r'%Y-%m-%d %H:%M:%S',
                csv_config=csv_config
            )
            listener.subscribe([self.w3, self.w4, self.w5, self.w1,self.w2,])
            
            with listener.start():
                count = 250
                for i in range(count):
                    self.w1._update_value(i*1.1)
                    self.w2._update_value(-2*i)
                    self.w3._update_value(3*i)
                    self.w4._update_value(i*4.4123)
                    self.w5._update_value(i%2==0)
                    listener._broadcast_update([self.w5, self.w1, self.w3, self.w4,  self.w2])  # Purposely out of order

                def all_received():
                    return listener.update_count == 5*count
                
                wait_cond(all_received, 0.5, "Not all received in time")


            self.assertTrue(os.path.exists(os.path.join(tempdir, 'my_file_0000.csv' )))
            self.assertTrue(os.path.exists(os.path.join(tempdir, 'my_file_0001.csv' )))
            self.assertTrue(os.path.exists(os.path.join(tempdir, 'my_file_0002.csv' )))
            self.assertFalse(os.path.exists(os.path.join(tempdir, 'my_file_0003.csv' )))

            #import ipdb; ipdb.set_trace()
            f1 = open(os.path.join(tempdir, 'my_file_0000.csv' ), 'r', encoding=csv_config.encoding, newline=csv_config.newline)
            f2 = open(os.path.join(tempdir, 'my_file_0001.csv' ), 'r', encoding=csv_config.encoding, newline=csv_config.newline)
            f3 = open(os.path.join(tempdir, 'my_file_0002.csv' ), 'r', encoding=csv_config.encoding, newline=csv_config.newline)
            
            for f in [f1,f2,f3]:
                nrow=100
                start=0
                if f is f2:
                    start=100
                if f is f3:
                    start=200
                    nrow=50
                reader = csv.reader(f, delimiter=csv_config.delimiter, quotechar=csv_config.quotechar, quoting=csv_config.quoting)
                rows = iter(reader)
                headers = next(rows)
                self.assertEqual(headers[0], 'datetime' )
                self.assertEqual(headers[1], 'time (ms)' )
                self.assertEqual(headers[-1], 'update flags' )
                all_watchables = sorted([self.w1, self.w2, self.w3, self.w4, self.w5], key=lambda x: x.display_path)
                index=2
                for watchable in all_watchables:
                    self.assertEqual(headers[index], watchable.display_path )
                    index+=1
                
                all_rows = list(rows)
                self.assertEqual(len(all_rows), nrow)
                for i in range(start, start+nrow):
                    row = all_rows[i-start]
                    datetime.strptime(row[0], r'%Y-%m-%d %H:%M:%S')    # check it can be parsed
                    float(row[1])  # ensure it can be parsed

                    for col in range(2, len(headers)-1):
                        if headers[col] == self.w1.display_path:
                            self.assertEqual(row[col], i*1.1)
                        elif headers[col] == self.w2.display_path:
                            self.assertEqual(row[col], -2*i)
                        elif headers[col] == self.w3.display_path:
                            self.assertEqual(row[col], 3*i)
                        elif headers[col] == self.w4.display_path:
                            self.assertEqual(row[col], i*4.4123)
                        elif headers[col] == self.w5.display_path:
                            self.assertEqual(row[col], 1 if i%2==0 else 0)
            
    def test_csv_writer_listener_bad_params(self):
        with TemporaryDirectory() as tempdir:
            with self.assertRaises(FileNotFoundError):
                CSVFileListener(
                    folder=os.path.join(tempdir, 'potato'),
                    filename='my_file'
                )
            
            with self.assertRaises(FileExistsError):
                ftest=os.path.join(tempdir, 'my_file_001.csv')
                open(ftest, 'w').close() # touch
                CSVFileListener(
                    folder=tempdir,
                    lines_per_file=10000,
                    filename='my_file'
                )
            os.unlink(ftest)


            ftest=os.path.join(tempdir, 'my_file_001.csv')
            open(ftest, 'w').close() # touch
            CSVFileListener(
                folder=tempdir,
                lines_per_file=None,
                filename='my_file'
            )
            os.unlink(ftest)


            with self.assertRaises(ValueError):
                CSVFileListener(
                    folder=tempdir,
                    lines_per_file=-1,
                    filename='my_file'
                )

            with self.assertRaises(ValueError):
                CSVFileListener(
                    folder=tempdir,
                    filename=os.path.join('xxx', 'yyy', 'my_file')
                )
            
            with self.assertRaises(TypeError):
                CSVFileListener(
                    folder=123,
                    filename='my_file'
                )
            
            with self.assertRaises(TypeError):
                CSVFileListener(
                    folder=tempdir,
                    lines_per_file='asd',
                    filename='my_file'
                )

            with self.assertRaises(TypeError):
                CSVFileListener(
                    folder=tempdir,
                    filename='my_file',
                    convert_bool_to_int='asd'
                )
            
            with self.assertRaises(TypeError):
                CSVFileListener(
                    folder=tempdir,
                    filename='my_file',
                    datetime_format=123
                )
            
            with self.assertRaises(ValueError):
                CSVFileListener(
                    folder=tempdir,
                    filename='my_file',
                    file_part_0pad=-1
                )

            with self.assertRaises(TypeError):
                CSVFileListener(
                    folder=tempdir,
                    filename='my_file',
                    file_part_0pad='asd'
                )
            
            with self.assertRaises(TypeError):
                CSVFileListener(
                    folder=tempdir,
                    filename='my_file',
                    csv_config='asd'
                )
            
            with self.assertRaises(sdk.exceptions.OperationFailure):
                listener = CSVFileListener(
                    folder=tempdir,
                    filename='my_file',
                    csv_config=CSVConfig(encoding='badencoding')
                )
                listener.start()

if __name__ == '__main__':
    unittest.main()
