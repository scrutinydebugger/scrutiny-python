#    test_tcp_client_handler.py
#        Test the TCP client handler (used by the server API)
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny.server.api.abstract_client_handler import ClientHandlerMessage
from scrutiny.server.api.tcp_client_handler import TCPClientHandler, TCPClientHandlerConfig
from scrutiny.tools.stream_datagrams import StreamMaker
from test import ScrutinyUnitTest
import socket
import time
import json
import queue
from scrutiny.tools.typing import *
import threading

class TestBadParams(ScrutinyUnitTest):
    def test_bad_params(self):
        with self.assertRaises(ValueError):
            TCPClientHandler(config={})
        with self.assertRaises(ValueError):
            TCPClientHandler(config=dict(host='localhost'))
        with self.assertRaises(ValueError):
            TCPClientHandler(config=dict(port=12345))
        
        TCPClientHandler(config=dict(host='localhost', port=12345))

class TestTCPClientHandler(ScrutinyUnitTest):
    
    def setUp(self) -> None:
        config:TCPClientHandlerConfig = {
            'host' : '127.0.0.1',
            'port' : 0
        }

        self.rx_event = threading.Event()
        self.handler = TCPClientHandler(config, rx_event=self.rx_event)
        self.handler.start()
        self.server_host = config['host']
        self.server_port = self.handler.get_port()
        self.stream_maker = StreamMaker(mtu=self.handler.STREAM_MTU, use_hash = self.handler.STREAM_USE_HASH)

    def wait_true(self, fn, timeout):
        t = time.perf_counter()
        while fn() is False and time.perf_counter() - t < timeout:
            time.sleep(0.01)
        self.assertTrue(fn())

    def assert_client_count_eq(self, n:int):
        self.wait_true(lambda : self.handler.get_number_client()==n, timeout=0.5)
        self.assertEqual(self.handler.get_number_client(), n)

    def serialize_dict(self, obj):
        return json.dumps(obj).encode('utf8')
    
    def deserialize_dict(self, data:bytes):
        return json.loads(data.decode('utf8'))


    def test_basic(self):
        obj = {
            'x' : 'y',
            'a' : 123
        }
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.assertEqual(self.handler.get_number_client(), 0)
        s.connect((self.server_host, self.server_port))
        self.assert_client_count_eq(1)

        s.send(self.stream_maker.encode(self.serialize_dict(obj)))
        self.wait_true(lambda : self.handler.available(), 1)
        msg = self.handler.recv()
        self.assertIsNotNone(msg.conn_id)
        self.assertEqual(msg.obj, obj)

        obj2 = {
            'aaa':2
        }
        self.handler.send(ClientHandlerMessage(conn_id=msg.conn_id, obj=obj2))
        
        s.settimeout(1)
        data = s.recv(4096)
        parser = self.handler.get_compatible_stream_parser()
        parser.parse(data)
        self.assertFalse(parser.queue().empty())
        obj2_received = self.deserialize_dict(parser.queue().get())
        self.assertEqual(obj2, obj2_received)
        self.assertTrue(parser.queue().empty())

        s.close()
        self.wait_true(lambda : self.handler.get_number_client()==0, timeout=0.5 )
        self.assert_client_count_eq(0)


    def test_multiclient(self):
        s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s3 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.assertEqual(self.handler.get_number_client(), 0)
        s1.connect((self.server_host, self.server_port))
        self.assert_client_count_eq(1)
        s2.connect((self.server_host, self.server_port))
        self.assert_client_count_eq(2)
        s3.connect((self.server_host, self.server_port))
        self.assert_client_count_eq(3)

        s2.send(self.stream_maker.encode(self.serialize_dict({'socket' : 2})))
        s3.send(self.stream_maker.encode(self.serialize_dict({'socket' : 3})))
        s1.send(self.stream_maker.encode(self.serialize_dict({'socket' : 1})))

        msg1 = self.handler.rx_queue.get(timeout=1)
        msg2 = self.handler.rx_queue.get(timeout=1)
        msg3 = self.handler.rx_queue.get(timeout=1)

        self.assertNotEqual(msg1.conn_id, msg2.conn_id)
        self.assertNotEqual(msg1.conn_id, msg3.conn_id)
        self.assertNotEqual(msg2.conn_id, msg3.conn_id)
        
        stats = self.handler.get_stats()
        self.assertEqual(stats.client_count, 3)
        self.assertEqual(stats.msg_received, 3)
        self.assertEqual(stats.msg_sent, 0)

        self.assertEqual(set([1,2,3]), set([x['socket'] for x in [msg1.obj, msg2.obj, msg3.obj]]))

        msg_per_socket:Dict[int, ClientHandlerMessage] = {}
        for msg in (msg1, msg2, msg3):
            msg_per_socket[msg.obj['socket']] = msg.conn_id

        self.handler.send(ClientHandlerMessage(conn_id=msg_per_socket[1], obj={'reply' : 1}))
        self.handler.send(ClientHandlerMessage(conn_id=msg_per_socket[2], obj={'reply' : 2}))
        self.handler.send(ClientHandlerMessage(conn_id=msg_per_socket[3], obj={'reply' : 3}))

        s1.settimeout(0.5)
        s2.settimeout(0.5)
        s3.settimeout(0.5)
        
        stream1 = self.handler.get_compatible_stream_parser()
        stream2 = self.handler.get_compatible_stream_parser()
        stream3 = self.handler.get_compatible_stream_parser()
        
        stream1.parse(s1.recv(4096))
        reply1 = self.deserialize_dict(stream1.queue().get())
        
        stream2.parse(s2.recv(4096))
        reply2 = self.deserialize_dict(stream2.queue().get())
        
        stream3.parse(s3.recv(4096))
        reply3 = self.deserialize_dict(stream3.queue().get())


        self.assertEqual(reply1, {'reply' : 1})
        self.assertEqual(reply2, {'reply' : 2})
        self.assertEqual(reply3, {'reply' : 3})

        stats = self.handler.get_stats()
        self.assertEqual(stats.client_count, 3)
        self.assertEqual(stats.msg_received, 3)
        self.assertEqual(stats.msg_sent, 3)

        self.assert_client_count_eq(3)
        s1.close()
        self.assert_client_count_eq(2)
        s2.close()
        self.assert_client_count_eq(1)
        s3.close()
        self.assert_client_count_eq(0)

        stats = self.handler.get_stats()
        self.assertEqual(stats.client_count, 0)
        self.assertEqual(stats.msg_received, 3)
        self.assertEqual(stats.msg_sent, 3)

    def test_send_to_inexistent_client(self):
        self.handler.send(ClientHandlerMessage("idonotexist", {}))  # Should not raise
    
    def test_send_unserializable(self):
        class MyObj:
            pass
        
        s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s1.connect((self.server_host, self.server_port))
        s1.send(self.stream_maker.encode(self.serialize_dict({})))

        msg = self.handler.rx_queue.get(timeout=1)
        
        with self.assertRaises(Exception):
            self.handler.send(ClientHandlerMessage(msg.conn_id, MyObj()))
    
    def test_send_gone_client(self):
        s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s1.connect((self.server_host, self.server_port))
        s1.send(self.stream_maker.encode(self.serialize_dict({})))

        msg = self.handler.rx_queue.get(timeout=1)
        self.assertTrue(self.handler.is_connection_active(msg.conn_id))
        
        s1.close()
        
        self.handler.send(ClientHandlerMessage(msg.conn_id, {}))
        self.wait_true(lambda: not self.handler.is_connection_active(msg.conn_id), 1)
        self.assertFalse(self.handler.is_connection_active(msg.conn_id))

    
    def test_close_cleanup(self):
        s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s1.connect((self.server_host, self.server_port))
        s1.send(self.stream_maker.encode(self.serialize_dict({})))

        self.wait_true(lambda : self.handler.available(), 1)
        self.handler.stop()
        self.assertFalse(self.handler.available())
        self.assertTrue(self.handler.rx_queue.empty())

        with self.assertRaises(OSError):
            # Don't know why required twice :S
            s1.send(b'123')
            s1.send(b'123')

    
    def test_rx_event(self):
        s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s1.connect((self.server_host, self.server_port))
        self.assertFalse(self.rx_event.is_set())
        s1.send(self.stream_maker.encode(self.serialize_dict({})))

        self.wait_true(lambda : self.rx_event.is_set(), 1)
        self.rx_event.clear()
        s1.send(self.stream_maker.encode(self.serialize_dict({})))
        self.wait_true(lambda : self.rx_event.is_set(), 1)

    def test_get_stats(self):
        stats = self.handler.get_stats()

        self.assertEqual(stats.client_count, 0)
        self.assertEqual(stats.input_datarate_byte_per_sec, 0)
        self.assertEqual(stats.output_datarate_byte_per_sec, 0)
        self.assertEqual(stats.msg_received, 0)
        self.assertEqual(stats.msg_sent, 0)

    def test_ignore_bad_json(self):
        s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.assertEqual(self.handler.get_number_client(), 0)
        s1.connect((self.server_host, self.server_port))
        self.assert_client_count_eq(1)


        s1.send(self.stream_maker.encode("I AM NOT JSON".encode('utf8')))

        with self.assertRaises(queue.Empty):
            self.handler.rx_queue.get(timeout=1)

        s1.send(self.stream_maker.encode(self.serialize_dict({'socket' : 1})))
        msg1 = self.handler.rx_queue.get(timeout=1)
        self.assertEqual(msg1.obj, {'socket' : 1})


    def tearDown(self) -> None:
        self.handler.stop()
