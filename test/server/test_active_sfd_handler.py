#    test_active_sfd_handler.py
#        Test the ActiveSFDHandler
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import unittest
from scrutiny.server.datastore.datastore_entry import EntryType

from scrutiny.server.device.device_handler import DeviceHandler
from scrutiny.server.active_sfd_handler import ActiveSFDHandler
from scrutiny.server.datastore import Datastore
from scrutiny.core.sfd_storage import SFDStorage
from test.artifacts import get_artifact


class StubbedDeviceHandler:
    connection_status: DeviceHandler.ConnectionStatus
    device_id: str

    def __init__(self, device_id, connection_status=DeviceHandler.ConnectionStatus.UNKNOWN):
        self.device_id = device_id
        self.connection_status = connection_status

    def get_connection_status(self):
        return self.connection_status

    def get_device_id(self):
        return self.device_id


class TestActiveSFDHandler(unittest.TestCase):

    def setUp(self):
        SFDStorage.use_temp_folder()
        self.sfd_filename = get_artifact('test_sfd_1.sfd')
        sfd = SFDStorage.install(self.sfd_filename, ignore_exist=True)
        self.firmware_id = sfd.get_firmware_id_ascii()

        self.device_handler = StubbedDeviceHandler(self.firmware_id, DeviceHandler.ConnectionStatus.DISCONNECTED)
        self.datastore = Datastore()

    def tearDown(self):
        SFDStorage.uninstall(self.firmware_id)
        SFDStorage.restore_storage()

    # Make sure the SFD is correctly loaded upon connection
    def test_autoload(self):
        self.sfd_handler = ActiveSFDHandler(self.device_handler, self.datastore, autoload=True)
        self.sfd_handler.process()
        self.assertEqual(self.datastore.get_entries_count(), 0)
        self.assertIsNone(self.sfd_handler.get_loaded_sfd())
        self.device_handler.connection_status = DeviceHandler.ConnectionStatus.CONNECTED_READY
        self.sfd_handler.process()
        self.assertIsNotNone(self.sfd_handler.get_loaded_sfd())

        sfd = self.sfd_handler.get_loaded_sfd()
        all_vars = list(sfd.get_vars_for_datastore())

        self.assertGreater(self.datastore.get_entries_count(EntryType.Var), 0)
        self.assertEqual(self.datastore.get_entries_count(EntryType.Var), len(all_vars))

        self.device_handler.connection_status = DeviceHandler.ConnectionStatus.DISCONNECTED
        self.sfd_handler.process()
        self.assertEqual(self.datastore.get_entries_count(EntryType.Var), 0)
        self.assertIsNone(self.sfd_handler.get_loaded_sfd())

    # Make sure the SFD is correctly loaded when requested (through API normally)
    def test_manual_load(self):
        self.sfd_handler = ActiveSFDHandler(self.device_handler, self.datastore, autoload=False)
        self.sfd_handler.process()
        self.assertEqual(self.datastore.get_entries_count(), 0)
        self.assertIsNone(self.sfd_handler.get_loaded_sfd())
        self.device_handler.connection_status = DeviceHandler.ConnectionStatus.CONNECTED_READY
        self.sfd_handler.process()
        self.assertIsNone(self.sfd_handler.get_loaded_sfd())
        self.assertEqual(self.datastore.get_entries_count(), 0)

        self.sfd_handler.request_load_sfd(self.firmware_id)
        self.sfd_handler.process()
        self.assertIsNotNone(self.sfd_handler.get_loaded_sfd())

        sfd = self.sfd_handler.get_loaded_sfd()
        all_vars = list(sfd.get_vars_for_datastore())

        self.assertGreater(self.datastore.get_entries_count(), 0)
        self.assertEqual(self.datastore.get_entries_count(EntryType.Var), len(all_vars))

        self.device_handler.connection_status = DeviceHandler.ConnectionStatus.DISCONNECTED
        self.sfd_handler.process()
        self.assertGreater(self.datastore.get_entries_count(EntryType.Var), 0)
        self.assertEqual(self.datastore.get_entries_count(EntryType.Var), len(all_vars))
