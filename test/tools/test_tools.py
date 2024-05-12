#    test_tools.py
#        Test various tools for the Python server application
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny.tools import Throttler
from scrutiny.tools.selectable_queue import *
import time
import math
import threading
from test import logger
from test import ScrutinyUnitTest


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

class TestSelectableQueue(ScrutinyUnitTest):

    def test_selectable_queue(self):
        nb_producer = 10
        nb_values = 10000

        class Producer:
            def __init__(self, index):
                self.count = 0
                self.finished = False
                self.thread = threading.Thread(target=self.task)
                self.queue = SelectableQueue()
                self.index = index
            
            def start(self):
                self.thread.start()
            
            def join(self):
                self.thread.join()
            
            def task(self):
                for i in range(nb_values):
                    if i%100 == 0:
                        time.sleep(0.01)
                    self.queue.put(i)
                self.finished = True
        
        producers = []
        queue_producer_map = {}
        values_bucket = {}
        for i in range(nb_producer):
            p = Producer(i)
            queue_producer_map[id(p.queue)] = p
            values_bucket[id(p)] = []
            producers.append(p)
        selector = QueueSelector([p.queue for p in producers], events=[SelectEvent.WRITE])

        for p in producers:
            p.start()
        
        all_finished = False
        last_check = False
        while not all_finished or last_check :
            selected = selector.wait()
            for q in selected:
                producer = queue_producer_map[id(q)]
                while not q.empty():
                    v = q.get(block=False)
                    values_bucket[id(producer)].append(v)
            # Values can be inserted between the last wait and the check below.
            # Hence the while loop condition that checks for is_notified()
            if last_check:  # Make sure to run only once after we,re finished
                break
            all_finished = all([p.finished for p in producers])
            if all_finished and selector.is_notified():
                last_check = True

            

        for p in producers:
            p.join()


        for p in producers:
            self.assertEqual(len(values_bucket[id(p)]), nb_values, f"producer={p.index}")
            for i in range(nb_values):
                self.assertEqual(i, values_bucket[id(p)][i], f"producer={p.index}")
        
        remainder = selector.wait(0.5)
        self.assertEqual(len(remainder), 0)

if __name__ == '__main__':
    import unittest
    unittest.main()
