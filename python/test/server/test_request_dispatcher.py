#    test_request_dispatcher.py
#        Test the request dispatcher.
#        Priorities, throttling, size limits.
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import unittest

from scrutiny.server.device.request_dispatcher import RequestDispatcher, RequestQueue, Throttler


class TestPriorityQueue(unittest.TestCase):
    def test_priority_queue_no_priority(self):
        q = RequestQueue()

        self.assertIsNone(q.peek())
        self.assertIsNone(q.pop())

        q.push(10)
        q.push(20)
        q.push(30)

        self.assertEqual(q.peek(), 10)
        self.assertEqual(q.peek(), 10)
        self.assertEqual(q.peek(), 10)

        self.assertEqual(q.pop(), 10)
        self.assertEqual(q.pop(), 20)
        self.assertEqual(q.pop(), 30)

        self.assertIsNone(q.pop())

    def test_priority_queuewith_priority(self):
        q = RequestQueue()

        q.push(10, priority=0)
        q.push(20, priority=1)
        q.push(30, priority=0)
        q.push(40, priority=1)
        q.push(50, priority=0)

        self.assertEqual(q.pop(), 20)
        self.assertEqual(q.pop(), 40)
        self.assertEqual(q.pop(), 10)
        self.assertEqual(q.pop(), 30)
        self.assertEqual(q.pop(), 50)

