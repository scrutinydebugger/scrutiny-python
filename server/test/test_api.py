import unittest
from server.api.API import API
from server.datastore import Datastore, DatastoreEntry
import queue
import time
import random
import string
import json
import uuid

class TestAPI(unittest.TestCase):

    def setUp(self):
        self.s2c = queue.Queue()
        self.c2s = queue.Queue()

        config = {
            'client_interface_type' : 'queue',
            'client_interface_config' : {
                'server_to_client_queue' : self.s2c,
                'client_to_server_queue' : self.c2s,
                'conn_id' : uuid.uuid4().hex
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

    def wait_and_load_response(self, timeout=0.4):
        json_str = self.wait_for_response(timeout)
        self.assertIsNotNone(json_str)
        return json.loads(json_str)

    def assert_no_error(self, response, *args, **kwargs):
        if 'cmd' in response:
            self.assertNotEqual(response['cmd'], API.Response.ERROR, *args, **kwargs)


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
        msg = {
            'cmd' : 'echo',
            'payload' : payload
        }
        self.c2s.put(json.dumps(msg))
        response = self.wait_and_load_response()

        self.assertEqual(response['cmd'], 'response_echo')
        self.assertEqual(response['payload'], payload)

    def test_get_watchable_count(self):
        var_entries = self.make_dummy_entries(3, type=DatastoreEntry.Type.eVar, prefix='var')
        alias_entries = self.make_dummy_entries(5, type=DatastoreEntry.Type.eAlias,  prefix='alias')

        # Add entries in the datastore that we will reread through the API
        self.datastore.add_entries_quiet(var_entries)
        self.datastore.add_entries_quiet(alias_entries)

        msg = {
            'cmd' : 'get_watchable_count'
        }

        self.c2s.put(json.dumps(msg))
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
        self.c2s.put(json.dumps(req))
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

    
    def test_get_watchable_list_with_type_filter(self):
        self.do_test_get_watchable_list_with_type_filter(None)
        self.do_test_get_watchable_list_with_type_filter('')
        self.do_test_get_watchable_list_with_type_filter([])
        self.do_test_get_watchable_list_with_type_filter(['var'])
        self.do_test_get_watchable_list_with_type_filter(['alias'])
        self.do_test_get_watchable_list_with_type_filter(['var', 'alias'])

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
        self.c2s.put(json.dumps(req))
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

    




