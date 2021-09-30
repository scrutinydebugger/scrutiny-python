import unittest
import queue
import time
import random
import string
import json
import uuid
import math

from scrutiny.server.api.API import API
from scrutiny.server.datastore import Datastore, DatastoreEntry
from scrutiny.server.api.dummy_client_handler import DummyConnection

#todo
# - Test rate limiter/data streamer



class TestAPI(unittest.TestCase):

    def setUp(self):
        self.connections = [DummyConnection(), DummyConnection(), DummyConnection()]
        for conn in self.connections:
            conn.open()

        config = {
            'client_interface_type' : 'dummy',
            'client_interface_config' : {
                'connections' : self.connections
            }
        }

        self.datastore = Datastore()
        self.api = API(config, self.datastore, None)
        self.api.start_listening()

    def tearDown(self):
        self.api.close()

    def wait_for_response(self, conn_idx=0, timeout = 0.4):
        t1 = time.time()
        self.api.process()
        while not self.connections[conn_idx].from_server_available():
            if time.time() - t1 >= timeout:
                break
            self.api.process()
            time.sleep(0.01)

        return self.connections[conn_idx].read_from_server()


    def wait_and_load_response(self, conn_idx=0, timeout=0.4):
        json_str = self.wait_for_response(conn_idx=conn_idx, timeout=timeout)
        self.assertIsNotNone(json_str)
        return json.loads(json_str)

    def send_request(self, req, conn_idx=0):
        self.connections[conn_idx].write_to_server(json.dumps(req))

    def assert_no_error(self, response, msg=None):
        if 'cmd' in response:
            if 'msg' in response and msg is None:
                msg = response['msg']
            self.assertNotEqual(response['cmd'], API.Command.Api2Client.ERROR_RESPONSE, msg)


    def make_dummy_entries(self, n, type=DatastoreEntry.Type.eVar, prefix='path'):
        entries = []
        for i in range(n):
            entry = DatastoreEntry(type, '%s_%d' % (prefix, i))
            entries.append(entry)
        return entries

    def make_random_string(self, n):
        letters = string.ascii_lowercase
        return''.join(random.choice(letters) for i in range(n))

# ===== Test section ===============
    def test_echo(self):
        payload = self.make_random_string(100)
        req = {
            'cmd' : 'echo',
            'payload' : payload
        }
        self.send_request(req)
        response = self.wait_and_load_response()

        self.assertEqual(response['cmd'], 'response_echo')
        self.assertEqual(response['payload'], payload)

    # Fetch count of var/alias. Ensure response is well formatted and accurate
    def test_get_watchable_count(self):
        var_entries = self.make_dummy_entries(3, type=DatastoreEntry.Type.eVar, prefix='var')
        alias_entries = self.make_dummy_entries(5, type=DatastoreEntry.Type.eAlias,  prefix='alias')

        # Add entries in the datastore that we will reread through the API
        self.datastore.add_entries_quiet(var_entries)
        self.datastore.add_entries_quiet(alias_entries)

        req = {
            'cmd' : 'get_watchable_count'
        }

        self.send_request(req)
        response = self.wait_and_load_response()
        self.assert_no_error(response)

        self.assertIn('cmd', response)
        self.assertIn('qty', response)
        self.assertIn('var', response['qty'])
        self.assertIn('alias', response['qty'])

        self.assertEqual(response['cmd'], 'response_get_watchable_count')
        self.assertEqual(response['qty']['var'], 3)
        self.assertEqual(response['qty']['alias'], 5)

    def assert_get_watchable_list_response_format(self, response):
        self.assertIn('cmd', response)
        self.assertIn('qty', response)
        self.assertIn('done', response)
        self.assertIn('var', response['qty'])
        self.assertIn('alias', response['qty'])
        self.assertIn('content', response)
        self.assertIn('var', response['content'])
        self.assertIn('alias', response['content'])
        self.assertEqual(response['cmd'], 'response_get_watchable_list')

    # Fetch list of var/alias. Ensure response is well formatted, accurate, complete, no duplicates
    def test_get_watchable_list_basic(self):
        var_entries = self.make_dummy_entries(3, type=DatastoreEntry.Type.eVar, prefix='var')
        alias_entries = self.make_dummy_entries(5, type=DatastoreEntry.Type.eAlias,  prefix='alias')

        expected_entries_in_response = {}
        for entry in var_entries:
            expected_entries_in_response[entry.get_id()] = entry
        for entry in alias_entries:
            expected_entries_in_response[entry.get_id()] = entry
        # Add entries in the datastore that we will reread through the API
        self.datastore.add_entries(var_entries)
        self.datastore.add_entries(alias_entries)

        req = {
            'cmd' : 'get_watchable_list'
        }
        self.send_request(req)
        response = self.wait_and_load_response()
        self.assert_no_error(response)

        self.assert_get_watchable_list_response_format(response)

        self.assertEqual(response['done'], True)
        self.assertEqual(response['qty']['var'], 3)
        self.assertEqual(response['qty']['alias'], 5)
        self.assertEqual(len(response['content']['var']), 3)
        self.assertEqual(len(response['content']['alias']), 5)

        read_id = []

        # Put all entries in a single list, paired with the name of the parent key.
        all_entries_same_level = [('var', entry) for entry in response['content']['var']] + [('alias', entry) for entry in response['content']['alias']]

        for item in all_entries_same_level:

            container = item[0]
            api_entry = item[1]

            self.assertIn('id', api_entry)
            self.assertIn('display_path', api_entry)

            self.assertIn(api_entry['id'], expected_entries_in_response)
            entry = expected_entries_in_response[api_entry['id']]

            self.assertEqual(entry.get_id(), api_entry['id'])
            self.assertEqual(entry.get_display_path(), api_entry['display_path'])
            if entry.get_type() == DatastoreEntry.Type.eVar:
                self.assertEqual('var', api_entry['type'])
            elif entry.get_type() == DatastoreEntry.Type.eAlias:
                self.assertEqual('alias', api_entry['type'])
            else:
                raise NotImplementedError('Test case does not supports entry type : %s' % (entry.get_type()))
            
            self.assertEqual(container, api_entry['type'])
            del expected_entries_in_response[api_entry['id']]

        self.assertEqual(len(expected_entries_in_response), 0)

    # Fetch list of var/alias and sets all sort of type filter.
    def test_get_watchable_list_with_type_filter(self):
        self.do_test_get_watchable_list_with_type_filter(None)
        self.do_test_get_watchable_list_with_type_filter('')
        self.do_test_get_watchable_list_with_type_filter([])
        self.do_test_get_watchable_list_with_type_filter(['var'])
        self.do_test_get_watchable_list_with_type_filter(['alias'])
        self.do_test_get_watchable_list_with_type_filter(['var', 'alias'])

    # Fetch list of var/alias and sets a type filter.
    def do_test_get_watchable_list_with_type_filter(self, type_filter):
        self.datastore.clear()
        var_entries = self.make_dummy_entries(3, type=DatastoreEntry.Type.eVar, prefix='var')
        alias_entries = self.make_dummy_entries(5, type=DatastoreEntry.Type.eAlias,  prefix='alias')

        no_filter = True if type_filter is None or type_filter == '' or isinstance(type_filter, list) and len(type_filter) == 0 else False

        nbr_expected_var = 0
        nbr_expected_alias = 0
        expected_entries_in_response = {}
        if no_filter or 'var' in type_filter:
            nbr_expected_var = len(var_entries)
            for entry in var_entries:
                expected_entries_in_response[entry.get_id()] = entry

        if no_filter or 'alias' in type_filter:
            nbr_expected_alias = len(alias_entries)
            for entry in alias_entries:
                expected_entries_in_response[entry.get_id()] = entry

        # Add entries in the datastore that we will reread through the API
        self.datastore.add_entries(var_entries)
        self.datastore.add_entries(alias_entries)

        req = {
            'cmd' : 'get_watchable_list',
            'filter' : {
                'type' : type_filter
            }
        }
        self.send_request(req)
        response = self.wait_and_load_response()
        self.assert_no_error(response, 'type_filter = %s' % (str(type_filter)))

        self.assert_get_watchable_list_response_format(response)

        self.assertEqual(response['done'], True)
        self.assertEqual(response['qty']['var'], nbr_expected_var)
        self.assertEqual(response['qty']['alias'], nbr_expected_alias)
        self.assertEqual(len(response['content']['var']), nbr_expected_var)
        self.assertEqual(len(response['content']['alias']), nbr_expected_alias)

        read_id = []

        # Put all entries in a single list, paired with the name of the parent key.
        all_entries_same_level = [('var', entry) for entry in response['content']['var']] + [('alias', entry) for entry in response['content']['alias']]

        for item in all_entries_same_level:

            container = item[0]
            api_entry = item[1]

            self.assertIn('id', api_entry)
            self.assertIn('display_path', api_entry)

            self.assertIn(api_entry['id'], expected_entries_in_response)
            entry = expected_entries_in_response[api_entry['id']]

            self.assertEqual(entry.get_id(), api_entry['id'])
            self.assertEqual(entry.get_display_path(), api_entry['display_path'])
            if entry.get_type() == DatastoreEntry.Type.eVar:
                self.assertEqual('var', api_entry['type'])
            elif entry.get_type() == DatastoreEntry.Type.eAlias:
                self.assertEqual('alias', api_entry['type'])
            else:
                raise NotImplementedError('Test case does not supports entry type : %s' % (entry.get_type()))
            
            self.assertEqual(container, api_entry['type'])
            del expected_entries_in_response[api_entry['id']]

        self.assertEqual(len(expected_entries_in_response), 0)


    # Fetch list of var/alias and sets a limit of items per response. 
    # List should be broken in multiple messages
    def test_get_watchable_list_with_item_limit(self):
        nVar = 19
        nAlias = 17
        max_per_response = 10
        var_entries = self.make_dummy_entries(nVar, type=DatastoreEntry.Type.eVar, prefix='var')
        alias_entries = self.make_dummy_entries(nAlias, type=DatastoreEntry.Type.eAlias,  prefix='alias')
        expected_entries_in_response = {}

        for entry in var_entries:
            expected_entries_in_response[entry.get_id()] = entry

        for entry in alias_entries:
            expected_entries_in_response[entry.get_id()] = entry

        # Add entries in the datastore that we will reread through the API
        self.datastore.add_entries(var_entries)
        self.datastore.add_entries(alias_entries)

        req = {
            'cmd' : 'get_watchable_list',
            'max_per_response' : max_per_response
        }

        self.send_request(req)
        responses = []
        nresponse = math.ceil((nVar+nAlias) / max_per_response)
        for i in range( nresponse):
            responses.append(self.wait_and_load_response())
        
        received_vars = []
        received_alias = []

        for i in range(len(responses)):
            response = responses[i]
            self.assert_no_error(response)
            self.assert_get_watchable_list_response_format(response)

            received_vars +=response['content']['var']
            received_alias += response['content']['alias']

            if i < len(responses)-1:
                self.assertEqual(response['done'], False)
                self.assertEqual(response['qty']['var'] + response['qty']['alias'], max_per_response)
                self.assertEqual(len(response['content']['var']) + len(response['content']['alias']), max_per_response)
            else:
                remaining_items = nVar + nAlias - (len(responses) - 1) * max_per_response
                self.assertEqual(response['done'], True)
                self.assertEqual(response['qty']['var'] + response['qty']['alias'], remaining_items)
                self.assertEqual(len(response['content']['var']) + len(response['content']['alias']), remaining_items)

        read_id = []

        # Put all entries in a single list, paired with the name of the parent key.
        all_entries_same_level = [('var', entry) for entry in received_vars] + [('alias', entry) for entry in received_alias]

        for item in all_entries_same_level:

            container = item[0]
            api_entry = item[1]

            self.assertIn('id', api_entry)
            self.assertIn('display_path', api_entry)

            self.assertIn(api_entry['id'], expected_entries_in_response)
            entry = expected_entries_in_response[api_entry['id']]

            self.assertEqual(entry.get_id(), api_entry['id'])
            self.assertEqual(entry.get_display_path(), api_entry['display_path'])
            if entry.get_type() == DatastoreEntry.Type.eVar:
                self.assertEqual('var', api_entry['type'])
            elif entry.get_type() == DatastoreEntry.Type.eAlias:
                self.assertEqual('alias', api_entry['type'])
            else:
                raise NotImplementedError('Test case does not supports entry type : %s' % (entry.get_type()))
            
            self.assertEqual(container, api_entry['type'])
            del expected_entries_in_response[api_entry['id']]

        self.assertEqual(len(expected_entries_in_response), 0)

    def assert_valid_value_update_message(self, msg):
        self.assert_no_error(msg)
        self.assertIn('cmd', msg)
        self.assertIn('updates', msg)

        self.assertEqual(msg['cmd'], 'watchable_update')
        self.assertIsInstance(msg['updates'], list)

        for update in msg['updates']:
            self.assertIn('id', update)
            self.assertIn('value', update)


    def test_subscribe_single_var(self):
        entries = self.make_dummy_entries(10, type=DatastoreEntry.Type.eVar, prefix='var')
        self.datastore.add_entries(entries)

        subscribed_entry = entries[2]
        req = {
            'cmd' : 'subscribe_watchable',
            'watchables' : [subscribed_entry.get_id()]
        }
    
        self.send_request(req, 0)
        response = self.wait_and_load_response()
        self.assert_no_error(response)

        self.assertIn('cmd', response)
        self.assertIn('watchables', response)
        self.assertIsInstance(response['watchables'], list)

        self.assertEqual(response['cmd'], 'response_subscribe_watchable')
        self.assertEqual(len(response['watchables']), 1)
        self.assertEqual(response['watchables'][0], subscribed_entry.get_id())

        self.assertIsNone(self.wait_for_response(timeout=0.2))

        self.datastore.set_value(subscribed_entry.get_id(), 1234)

        var_update_msg = self.wait_and_load_response(timeout=0.5)
        self.assert_valid_value_update_message(var_update_msg)
        self.assertEqual(len(var_update_msg['updates']), 1)

        update = var_update_msg['updates'][0]

        self.assertEqual(update['id'], subscribed_entry.get_id())
        self.assertEqual(update['value'], 1234)

    # Make sure that we can unsubscribe correctly to a variable and value update stops
    def test_subscribe_unsubscribe(self):
        entries = self.make_dummy_entries(10, type=DatastoreEntry.Type.eVar, prefix='var')
        self.datastore.add_entries(entries)
        subscribed_entry = entries[2]
        subscribe_cmd = {
            'cmd' : 'subscribe_watchable',
            'watchables' : [subscribed_entry.get_id()]
        }

        # Subscribe through conn 0
        self.send_request(subscribe_cmd, 0)
        response = self.wait_and_load_response(0)
        self.assert_no_error(response)

        unsubscribe_cmd = {
            'cmd' : 'unsubscribe_watchable',
            'watchables' : [subscribed_entry.get_id()]
        }

        self.send_request(unsubscribe_cmd, 0)
        response = self.wait_and_load_response(0)
        self.assert_no_error(response)
        
        self.datastore.set_value(subscribed_entry.get_id(), 1111)
        self.assertIsNone(self.wait_for_response(0, timeout=0.1))

    # Make sure that the streamer send the value update once if many update happens before the value is outputted to the client.
    def test_do_not_send_duplicate_changes(self):
        entries = self.make_dummy_entries(10, type=DatastoreEntry.Type.eVar, prefix='var')
        self.datastore.add_entries(entries)

        subscribed_entry = entries[2]
        req = {
            'cmd' : 'subscribe_watchable',
            'watchables' : [subscribed_entry.get_id()]
        }

        self.send_request(req, 0)
        response = self.wait_and_load_response(0)
        self.assert_no_error(response)

        self.api.streamer.freeze_connection(self.connections[0].get_id())
        self.datastore.set_value(subscribed_entry.get_id(), 1234)
        self.datastore.set_value(subscribed_entry.get_id(), 4567)
        self.api.streamer.unfreeze_connection(self.connections[0].get_id())

        var_update_msg = self.wait_and_load_response(timeout=0.5)
        self.assert_valid_value_update_message(var_update_msg)
        self.assertEqual(len(var_update_msg['updates']), 1)     # Only one update

        self.assertEqual(var_update_msg['updates'][0]['id'], subscribed_entry.get_id())
        self.assertEqual(var_update_msg['updates'][0]['value'], 4567)   # Got latest value

        self.assertIsNone(self.wait_for_response(0, timeout=0.1))   # No more message to send

    