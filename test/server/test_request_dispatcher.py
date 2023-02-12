#    test_request_dispatcher.py
#        Test the request dispatcher.
#        Priorities, throttling, size limits.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

from scrutiny.server.device.request_dispatcher import RequestDispatcher, RequestQueue
from scrutiny.server.protocol.commands import DummyCommand
from scrutiny.server.protocol import Request, Response, ResponseCode
from test import ScrutinyUnitTest


class TestPriorityQueue(ScrutinyUnitTest):
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


class TestRequestDispatcher(ScrutinyUnitTest):
    def setUp(self):
        self.success_list = []
        self.failure_list = []

    def make_payload(self, size):
        return b'\x01' * size

    def make_dummy_request(self, subfn=0, payload=b'', response_payload_size=0):
        return Request(DummyCommand, subfn=subfn, payload=payload, response_payload_size=response_payload_size)

    def success_callback(self, request, response, params=None):
        self.success_list.append({
            'request': request,
            'response_code': response.code,
            'response_data': response.payload,
            'params': params
        })

    def failure_callback(self, request, params=None):
        self.failure_list.append({
            'request': request,
            'params': params
        })

    def test_priority_respect(self):
        dispatcher = RequestDispatcher()
        req1 = self.make_dummy_request()
        req2 = self.make_dummy_request()
        req3 = self.make_dummy_request()

        dispatcher.register_request(request=req1, success_callback=self.success_callback, failure_callback=self.failure_callback, priority=0)
        dispatcher.register_request(request=req2, success_callback=self.success_callback, failure_callback=self.failure_callback, priority=1)
        dispatcher.register_request(request=req3, success_callback=self.success_callback, failure_callback=self.failure_callback, priority=0)

        self.assertEqual(dispatcher.pop_next().request, req2)
        self.assertEqual(dispatcher.pop_next().request, req1)
        self.assertEqual(dispatcher.pop_next().request, req3)

    def test_callbacks(self):
        dispatcher = RequestDispatcher()
        req1 = self.make_dummy_request()
        req2 = self.make_dummy_request()

        dispatcher.register_request(request=req1, success_callback=self.success_callback,
                                    failure_callback=self.failure_callback, success_params=[1, 2], failure_params=[3, 4])
        dispatcher.register_request(request=req2, success_callback=self.success_callback,
                                    failure_callback=self.failure_callback, success_params=[5, 6], failure_params=[7, 8])

        record = dispatcher.pop_next()
        record.complete(success=True, response=Response(DummyCommand, subfn=0, code=ResponseCode.OK, payload=b'data1'))
        record = dispatcher.pop_next()
        record.complete(success=False)

        self.assertEqual(len(self.success_list), 1)
        self.assertEqual(self.success_list[0]['request'], req1)
        self.assertEqual(self.success_list[0]['response_code'], ResponseCode.OK)
        self.assertEqual(self.success_list[0]['response_data'], b"data1")
        self.assertEqual(self.success_list[0]['params'], [1, 2])

        self.assertEqual(len(self.failure_list), 1)
        self.assertEqual(self.failure_list[0]['request'], req2)
        self.assertEqual(self.failure_list[0]['params'], [7, 8])

    def test_drops_overflowing_requests(self):
        dispatcher = RequestDispatcher()
        req1 = self.make_dummy_request(payload=self.make_payload(128), response_payload_size=256)
        req2 = self.make_dummy_request(payload=self.make_payload(129), response_payload_size=256)
        req3 = self.make_dummy_request(payload=self.make_payload(128), response_payload_size=257)
        dispatcher.set_size_limits(max_request_payload_size=128, max_response_payload_size=256)

        dispatcher.logger.disabled = True
        dispatcher.register_request(request=req1, success_callback=self.success_callback, failure_callback=self.failure_callback)
        dispatcher.register_request(request=req2, success_callback=self.success_callback, failure_callback=self.failure_callback)
        dispatcher.register_request(request=req3, success_callback=self.success_callback, failure_callback=self.failure_callback)
        dispatcher.logger.disabled = False

        self.assertEqual(dispatcher.pop_next().request, req1)
        self.assertIsNone(dispatcher.pop_next())


if __name__ == '__main__':
    import unittest
    unittest.main()
