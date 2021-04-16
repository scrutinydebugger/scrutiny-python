import unittest
from server.api.API import API
from server.datastore import Datastore
import queue
import time
import random
import string
import json

class TestAPI(unittest.TestCase):

    def setUp(self):
        self.s2c = queue.Queue()
        self.c2s = queue.Queue()

        config = {
            'client_interface_type' : 'queue',
            'client_interface_config' : {
                'server_to_client_queue' : self.s2c,
                'client_to_server_queue' : self.c2s,
            }
        }

        self.datastore = Datastore()
        self.api = API(config, self.datastore)
        self.api.start_listening()

    def tearDown(self):
        self.api.close()

    def wait_for_response(self, timeout = 0.4):
        t1 = time.time()
        while self.s2c.empty():
            if time.time() - t1 >= timeout:
                break
            self.api.process()
            time.sleep(0.01)

        try:
            popped = self.s2c.get_nowait()
            return popped
        except:
            pass

    def make_random_string(self, n):
        letters = string.ascii_lowercase
        return''.join(random.choice(letters) for i in range(n))

    def test_echo(self):
        payload = self.make_random_string(100)
        msg = {
            'cmd' : 'echo',
            'payload' : payload
        }
        self.c2s.put(json.dumps(msg))
        response_raw = self.wait_for_response()
        self.assertIsNotNone(response_raw)
        response = json.loads(response_raw)

        self.assertEqual(response['cmd'], 'echo_response')
        self.assertEqual(response['payload'], payload)

