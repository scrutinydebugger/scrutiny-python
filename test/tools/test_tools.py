#    test_tools.py
#        Test various tools for the Python server application
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny.tools import Throttler, SuppressException
from scrutiny.tools.thread_enforcer import enforce_thread, register_thread, thread_func
import time
import math
from test import logger
from test import ScrutinyUnitTest
import threading

class TestThrottler(ScrutinyUnitTest):

    def test_throttler_measurement(self):
        bitrate = 5000
        throttler = Throttler()
        throttler.set_bitrate(bitrate)
        throttler.enable()

        runtime = 5
        tstart = time.time()
        time_axis = []
        data_axis = []
        write_chunk = bitrate / 30    # Keep smaller than 60 because of thread resolution of 16ms
        while time.time() - tstart < runtime:
            throttler.process()
            if throttler.allowed(write_chunk):
                throttler.consume_bandwidth(write_chunk)
                time_axis.append(time.time())
                data_axis.append(write_chunk)
            time.sleep(0.001)

        dt = time_axis[-1] - time_axis[0]
        total = 0
        for x in data_axis:
            total += x

        measured_bitrate = total / dt
        logger.info('Measured bitrate = %0.2fkbps. Target = %0.2fkbps' % (measured_bitrate / 1000.0, bitrate / 1000.0))
        self.assertGreater(measured_bitrate, bitrate * 0.8)
        self.assertLess(measured_bitrate, bitrate * 1.2)

        # Now make sure that the buffer won't be overloaded
        buffer_estimation = []
        buffer_peak = 0
        for i in range(len(data_axis)):

            if len(buffer_estimation) == 0:
                buffer_estimation.append(data_axis[i])
            else:
                dt = time_axis[i] - time_axis[i - 1]
                buffer_estimation.append(buffer_estimation[-1] + data_axis[i] - bitrate * dt)
                buffer_peak = max(buffer_peak, buffer_estimation[-1])

        logger.info('Maximum buffer peak = %dbits' % (math.ceil(buffer_peak)))

class TestTools(ScrutinyUnitTest):
    def test_update_dict_recursive(self):
        from scrutiny.tools import update_dict_recursive
        d = {
            'x' : 'y',
            'aaa' : {
                'xxx' : 1,
                'yyy' : [1,2,3],
                'zzz' : {
                    'hello' : 'world'
                }
            }
        }
        
        update_dict_recursive(d, {'b' : 2})
        update_dict_recursive(d, {'aaa' : {'xxx': 3,  'bbb' : 'ccc', 'zzz': {'potato' : 'tomato'} }})

        expected_dict = {
            'b' : 2,
            'x' : 'y',
            'aaa' : {
                'xxx' : 3,
                'bbb' : 'ccc',
                'yyy' : [1,2,3],
                'zzz' : {
                    'hello' : 'world',
                    'potato' : 'tomato'
                }
            }
        }

        self.assertEqual(d, expected_dict)


class TestThreadEnforcer(ScrutinyUnitTest):
    def test_thread_enforce(self):
        
        @enforce_thread("AAA")
        def func_AAA():
            pass

        @enforce_thread("BBB")
        def func_BBB():
            pass

        with self.assertRaises(Exception):
            func_AAA()

        register_thread("AAA")  # register self thread
        func_AAA()

        bbb_started = threading.Event()
        call_bbb = threading.Event()
        bbb_called = threading.Event()
        exit_bbb = threading.Event()


        @thread_func("BBB")
        def BBB_thread_func():
            bbb_started.set()
            
            with self.assertRaises(Exception):
                func_AAA()
            
            call_bbb.wait(2)
            func_BBB()
            bbb_called.set()
            exit_bbb.wait(2)


        BBB2_started = threading.Event()
        
        @thread_func("BBB")
        def duplicate_BBB():
            BBB2_started.set()

        thread_BBB = threading.Thread(target=BBB_thread_func, daemon=True)
        thread_BBB.start()
        bbb_started.wait(1)

        with self.assertRaises(Exception):
            func_BBB()
        
        call_bbb.set()
        bbb_called.wait(1)
        self.assertTrue(bbb_called.is_set())
        self.assertTrue(thread_BBB.is_alive())

        BBB2_dead = threading.Event()
        def duplicate_BBB_no_exc():
            try:
                duplicate_BBB()
            except Exception:
                BBB2_dead.set()
            

        thread_BBB2 = threading.Thread(target=duplicate_BBB_no_exc, daemon=True)
        thread_BBB2.start()
        BBB2_dead.wait(1)

        self.assertFalse(BBB2_started.is_set())
        self.assertTrue(BBB2_dead.is_set())
        thread_BBB2.join(1)
        self.assertFalse(thread_BBB2.is_alive())
        exit_bbb.set()


    def test_ignore_error(self):
        with self.assertRaises(ValueError):
            with SuppressException(TypeError):
                raise TypeError("aaa")
            
            with SuppressException(TypeError):
                raise ValueError("bbb")
            
        
        with SuppressException(TypeError, NotImplementedError):
            raise NotImplementedError("aaa")
        
        with SuppressException():
            raise ValueError("aaa")

        

if __name__ == '__main__':
    import unittest
    unittest.main()
