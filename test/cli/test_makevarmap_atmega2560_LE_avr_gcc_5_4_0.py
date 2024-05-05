#    test_makevarmap_atmega2560_LE_avr_gcc_5_4_0.py
#        Test that we can make a valid VarMap out of a known binary : scrutiny-nsec2024.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import unittest

from scrutiny.core.varmap import VarMap
from scrutiny.core.basic_types import *
from scrutiny.core.variable import *
from scrutiny.core.bintools.elf_dwarf_var_extractor import ElfDwarfVarExtractor
from scrutiny.core.memory_content import MemoryContent
from scrutiny.exceptions import EnvionmentNotSetUpException
from test import SkipOnException
from test.artifacts import get_artifact
from test import ScrutinyUnitTest

from typing import Optional


known_enums = {
    "Bno055DriverError": {
        "NO_ERROR": 0,
        "NO_INIT": 1,
        "NOT_READY": 2,
        "FAILED_READ_INFO": 3,
        "INTERRUPT_READ_ENABLED": 4
    },

    "SystemStatusCode": {
        "SystemIdle": 0,
        "SystemError": 1,
        "InitializingPeripherals": 2,
        "SystemInitialization": 3,
        "ExecutingSelfTest": 4,
        "SensorFusionAlgorithmRunning": 5,
        "SystemRunningWithoutSensorFusion": 6
    },

    "SystemErrorCode": {
        "NoError": 0,
        "PeripheralInitError": 1,
        "SystemInitError": 2,
        "SelfTestFailed": 3,
        "RegisterMapValueOOR": 4,
        "RegisterMapAddrOOR": 5,
        "RegisterMapWriteError": 6,
        "LowPowerNotAvailableForSelectedOM": 7,
        "AccelerometerPowerModeNotAvailable": 8,
        "FusionAlgorithmError": 9,
        "SensorConfigurationError": 10
    },

    "InterruptReadState": {
        "IDLE": 0,
        "READ_ACCEL": 1,
        "READ_GYRO": 2,
        "READ_MAG": 3,
        "ERROR": 4
    },

    "InterruptReadMode": {
        "SINGLE": 0,
        "CONTINUOUS": 1
    },

    "CommHandlerState": {
        "Idle": 0,
        "Receiving": 1,
        "Transmitting": 2
    },

    "CommHandlerRxFSMState": {
        "WaitForCommand": 0,
        "WaitForSubfunction": 1,
        "WaitForLength": 2,
        "WaitForData": 3,
        "WaitForCRC": 4,
        "WaitForProcess": 5,
        "Error": 6
    },

    "CommHandlerRxError": {
        "None": 0,
        "Overflow": 1,
        "Disabled": 2
    },

    "CommHandlerTxError": {
        "None": 0,
        "Overflow": 1,
        "Busy": 2,
        "Disabled": 3
    },

    "DataloggerState": {
        "IDLE": 0,
        "CONFIGURED": 1,
        "ARMED": 2,
        "TRIGGERED": 3,
        "ACQUISITION_COMPLETED": 4,
        "ERROR": 5
    },

    "LoggableType": {
        "MEMORY": 0,
        "RPV": 1,
        "TIME": 2
    },

    "SupportedTriggerConditions": {
        "AlwaysTrue": 0,
        "Equal": 1,
        "NotEqual": 2,
        "LessThan": 3,
        "LessOrEqualThan": 4,
        "GreaterThan": 5,
        "GreaterOrEqualThan": 6,
        "ChangeMoreThan": 7,
        "IsWithin": 8
    },

    "OperandType": {
        "LITERAL": 0,
        "VAR": 1,
        "VARBIT": 2,
        "RPV": 3
    },

    "DataloggingError": {
        "NoError": 0,
        "UnexpectedRelease": 1,
        "UnexpectedClaim": 2
    },

    "Main2LoopMessageID" : {
        "RELEASE_DATALOGGER_OWNERSHIP": 0,
        "TAKE_DATALOGGER_OWNERSHIP": 1,
        "DATALOGGER_ARM_TRIGGER": 2,
        "DATALOGGER_DISARM_TRIGGER": 3
    },

    "Loop2MainMessageID" : {
        "DATALOGGER_OWNERSHIP_TAKEN": 0,
        "DATALOGGER_OWNERSHIP_RELEASED": 1,
        "DATALOGGER_DATA_ACQUIRED": 2,
        "DATALOGGER_STATUS_UPDATE": 3
    }
}


class TestMakeVarMap_ATMega2560_LE_avr_gcc_5_4_0(ScrutinyUnitTest):
    init_exception: Optional[Exception]
    bin_filename = get_artifact('scrutiny-nsec2024_untagged.elf')

    @classmethod
    def setUpClass(cls):
        cls.init_exception = None
        try:
            extractor = ElfDwarfVarExtractor(cls.bin_filename, cppfilt='avr-c++filt')
            varmap = extractor.get_varmap()
            cls.varmap = VarMap(varmap.get_json())
        except Exception as e:
            cls.init_exception = e  # Let's remember the exception and throw it for each test for good logging.

    @SkipOnException(EnvionmentNotSetUpException)
    def setUp(self) -> None:
        if self.init_exception is not None:
            raise self.init_exception

    def load_var(self, fullname):
        return self.varmap.get_var(fullname)

    def assert_var(self, fullname, thetype, addr=None, bitsize=None, bitoffset=None, enum:Optional[str]=None):
        v = self.load_var(fullname)
        self.assertEqual(thetype, v.get_type())

        if bitsize is not None:
            self.assertEqual(v.bitsize, bitsize)

        if bitoffset is not None:
            self.assertEqual(v.bitoffset, bitoffset)

        if addr is not None:
            self.assertEqual(addr, v.get_address())

        if enum is not None:
            self.assertIn(enum, known_enums)
            self.assertIsNotNone(v.enum)
            for key, value in known_enums[enum].items():
                value2 = v.enum.get_value(key)
                self.assertIsNotNone(value2)
                self.assertEqual(value2, value)
        else:
            self.assertIsNone(v.enum)

        return v

    def assert_is_enum(self, v):
        self.assertIsNotNone(v.enum)

    def assert_has_enum(self, v, name: str, value: int):
        self.assert_is_enum(v)
        value2 = v.enum.get_value(name)
        self.assertIsNotNone(value2)
        self.assertEqual(value2, value)

    def test_env(self):
        self.assertEqual(self.varmap.endianness, Endianness.Little)

    def test_main_cpp(self):
        self.assert_var('/static/main.cpp/task_100hz()/var_100hz', EmbeddedDataType.uint32)
        self.assert_var('/static/main.cpp/task_1hz()/var_1hz', EmbeddedDataType.uint32)
        self.assert_var('/static/main.cpp/task_1hz()/led_state', EmbeddedDataType.sint16)
        
        self.assert_var('/static/main.cpp/loop/last_timestamp_us', EmbeddedDataType.uint32)
        self.assert_var('/static/main.cpp/loop/last_timestamp_task_1hz_us', EmbeddedDataType.uint32)
        self.assert_var('/static/main.cpp/loop/last_timestamp_task_100hz_us', EmbeddedDataType.uint32)

    def test_loop_handlers(self):
        self.assert_var('/global/task_idle_loop_handler/m_timebase/m_time_100ns', EmbeddedDataType.uint32)
        self.assert_var('/global/task_idle_loop_handler/m_main2loop_msg/m_written', EmbeddedDataType.boolean)
        self.assert_var('/global/task_idle_loop_handler/m_main2loop_msg/data/message_id', EmbeddedDataType.uint8, enum='Main2LoopMessageID')
        self.assert_var('/global/task_idle_loop_handler/m_loop2main_msg/m_written', EmbeddedDataType.boolean)
        self.assert_var('/global/task_idle_loop_handler/m_loop2main_msg/data/message_id', EmbeddedDataType.uint8, enum='Loop2MainMessageID')
        
        # union not supported yet
#       self.assert_var('/global/task_idle_loop_handler/m_loop2main_msg/data/data/datalogger_status_update/state', EmbeddedDataType.uint8, enum='DataloggerState')
#       self.assert_var('/global/task_idle_loop_handler/m_loop2main_msg/data/data/datalogger_status_update/bytes_to_acquire_from_trigger_to_completion', EmbeddedDataType.uint32)
#       self.assert_var('/global/task_idle_loop_handler/m_loop2main_msg/data/data/datalogger_status_update/write_counter_since_trigger', EmbeddedDataType.uint32)

        self.assert_var('/global/task_idle_loop_handler/m_owns_datalogger', EmbeddedDataType.boolean)
        self.assert_var('/global/task_idle_loop_handler/m_datalogger_data_acquired', EmbeddedDataType.boolean)
        self.assert_var('/global/task_idle_loop_handler/m_support_datalogging', EmbeddedDataType.boolean)


        self.assert_var('/global/task_100hz_loop_handler/m_timestep_100ns', EmbeddedDataType.uint32)
        self.assert_var('/global/task_100hz_loop_handler/m_timebase/m_time_100ns', EmbeddedDataType.uint32)
        self.assert_var('/global/task_100hz_loop_handler/m_main2loop_msg/m_written', EmbeddedDataType.boolean)
        self.assert_var('/global/task_100hz_loop_handler/m_main2loop_msg/data/message_id', EmbeddedDataType.uint8, enum='Main2LoopMessageID')
        self.assert_var('/global/task_100hz_loop_handler/m_loop2main_msg/m_written', EmbeddedDataType.boolean)
        self.assert_var('/global/task_100hz_loop_handler/m_loop2main_msg/data/message_id', EmbeddedDataType.uint8, enum='Loop2MainMessageID')
        # union not supported yet
#       self.assert_var('/global/task_100hz_loop_handler/m_loop2main_msg/data/data/datalogger_status_update/state', EmbeddedDataType.uint8, enum='DataloggerState')
#       self.assert_var('/global/task_100hz_loop_handler/m_loop2main_msg/data/data/datalogger_status_update/bytes_to_acquire_from_trigger_to_completion', EmbeddedDataType.uint32)
#       self.assert_var('/global/task_100hz_loop_handler/m_loop2main_msg/data/data/datalogger_status_update/write_counter_since_trigger', EmbeddedDataType.uint32)

        self.assert_var('/global/task_100hz_loop_handler/m_owns_datalogger', EmbeddedDataType.boolean)
        self.assert_var('/global/task_100hz_loop_handler/m_datalogger_data_acquired', EmbeddedDataType.boolean)
        self.assert_var('/global/task_100hz_loop_handler/m_support_datalogging', EmbeddedDataType.boolean)
       

        self.assert_var('/global/task_20hz_loop_handler/m_timestep_100ns', EmbeddedDataType.uint32)
        self.assert_var('/global/task_20hz_loop_handler/m_timebase/m_time_100ns', EmbeddedDataType.uint32)
        self.assert_var('/global/task_20hz_loop_handler/m_main2loop_msg/m_written', EmbeddedDataType.boolean)
        self.assert_var('/global/task_20hz_loop_handler/m_main2loop_msg/data/message_id', EmbeddedDataType.uint8, enum='Main2LoopMessageID')
        self.assert_var('/global/task_20hz_loop_handler/m_loop2main_msg/m_written', EmbeddedDataType.boolean)
        self.assert_var('/global/task_20hz_loop_handler/m_loop2main_msg/data/message_id', EmbeddedDataType.uint8, enum='Loop2MainMessageID')
        # union not supported yet
#       self.assert_var('/global/task_20hz_loop_handler/m_loop2main_msg/data/data/datalogger_status_update/state', EmbeddedDataType.uint8, enum='DataloggerState')
#       self.assert_var('/global/task_20hz_loop_handler/m_loop2main_msg/data/data/datalogger_status_update/bytes_to_acquire_from_trigger_to_completion', EmbeddedDataType.uint32)
#       self.assert_var('/global/task_20hz_loop_handler/m_loop2main_msg/data/data/datalogger_status_update/write_counter_since_trigger', EmbeddedDataType.uint32)

        self.assert_var('/global/task_20hz_loop_handler/m_owns_datalogger', EmbeddedDataType.boolean)
        self.assert_var('/global/task_20hz_loop_handler/m_datalogger_data_acquired', EmbeddedDataType.boolean)
        self.assert_var('/global/task_20hz_loop_handler/m_support_datalogging', EmbeddedDataType.boolean)
       

    def test_main_handler(self):
        #self.assert_var("/static/scrutiny_integration.cpp/config/m_rx_buffer", EmbeddedDataType.pointer)
        self.assert_var("/static/scrutiny_integration.cpp/config/m_rx_buffer_size", EmbeddedDataType.uint16)
        #self.assert_var("/static/scrutiny_integration.cpp/config/m_tx_buffer", EmbeddedDataType.pointer)
        self.assert_var("/static/scrutiny_integration.cpp/config/m_tx_buffer_size", EmbeddedDataType.uint16)
        #self.assert_var("/static/scrutiny_integration.cpp/config/m_forbidden_address_ranges", EmbeddedDataType.pointer)
        self.assert_var("/static/scrutiny_integration.cpp/config/m_forbidden_range_count", EmbeddedDataType.uint8)
        #self.assert_var("/static/scrutiny_integration.cpp/config/m_readonly_address_ranges", EmbeddedDataType.pointer)
        self.assert_var("/static/scrutiny_integration.cpp/config/m_readonly_range_count", EmbeddedDataType.uint8)
        #self.assert_var("/static/scrutiny_integration.cpp/config/m_rpvs", EmbeddedDataType.pointer)
        self.assert_var("/static/scrutiny_integration.cpp/config/m_rpv_count", EmbeddedDataType.uint16)
        #self.assert_var("/static/scrutiny_integration.cpp/config/m_rpv_read_callback", EmbeddedDataType.pointer)
        #self.assert_var("/static/scrutiny_integration.cpp/config/m_rpv_write_callback", EmbeddedDataType.pointer)
        #self.assert_var("/static/scrutiny_integration.cpp/config/m_loops", EmbeddedDataType.pointer)
        self.assert_var("/static/scrutiny_integration.cpp/config/m_loop_count", EmbeddedDataType.uint8)
        #self.assert_var("/static/scrutiny_integration.cpp/config/m_user_command_callback", EmbeddedDataType.pointer)
        #self.assert_var("/static/scrutiny_integration.cpp/config/m_datalogger_buffer", EmbeddedDataType.pointer)
        self.assert_var("/static/scrutiny_integration.cpp/config/m_datalogger_buffer_size", EmbeddedDataType.uint16)
        #self.assert_var("/static/scrutiny_integration.cpp/config/m_datalogger_trigger_callback", EmbeddedDataType.pointer)

        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_timebase/m_time_100ns", EmbeddedDataType.uint32)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_state", EmbeddedDataType.uint8, enum='CommHandlerState' )
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_enabled", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_session_id", EmbeddedDataType.uint32)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_session_active", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_heartbeat_timestamp", EmbeddedDataType.uint32)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_last_heartbeat_challenge", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_first_heartbeat_received", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_rx_buffer_size", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_tx_buffer_size", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_active_request/command_id", EmbeddedDataType.uint8)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_active_request/subfunction_id", EmbeddedDataType.uint8)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_active_request/data_length", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_active_request/data_max_length", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_active_request/crc", EmbeddedDataType.uint32)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_rx_state", EmbeddedDataType.uint8, enum='CommHandlerRxFSMState')
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_rx_error", EmbeddedDataType.uint8, enum='CommHandlerRxError')
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_request_received", EmbeddedDataType.boolean)
        # Missing union support
        #self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_per_state_data/crc_bytes_received", EmbeddedDataType.uint8)
        #self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_per_state_data/length_bytes_received", EmbeddedDataType.uint8)
        #self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_per_state_data/data_bytes_received", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_last_rx_timestamp", EmbeddedDataType.uint32)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_active_response/command_id", EmbeddedDataType.uint8)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_active_response/subfunction_id", EmbeddedDataType.uint8)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_active_response/response_code", EmbeddedDataType.uint8)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_active_response/data_length", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_active_response/data_max_length", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_active_response/crc", EmbeddedDataType.uint32)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_nbytes_to_send", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_nbytes_sent", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_tx_error", EmbeddedDataType.uint8, enum='CommHandlerTxError')
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_processing_request", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_disconnect_pending", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_config/max_bitrate", EmbeddedDataType.uint32)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_config/session_counter_seed", EmbeddedDataType.uint32)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_config/memory_write_enable", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_config/m_rx_buffer_size", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_config/m_tx_buffer_size", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_config/m_forbidden_range_count", EmbeddedDataType.uint8)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_config/m_readonly_range_count", EmbeddedDataType.uint8)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_config/m_rpv_count", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_config/m_loop_count", EmbeddedDataType.uint8)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_config/m_datalogger_buffer_size", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_enabled", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_process_again_timestamp_taken", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_process_again_timestamp", EmbeddedDataType.uint32)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_buffer_size", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_state", EmbeddedDataType.uint8, enum='DataloggerState')
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_trigger_timestamp", EmbeddedDataType.uint32)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_trigger_cursor_location", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_remaining_data_to_write", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_manual_trigger", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_config/items_count", EmbeddedDataType.uint8)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_config/decimation", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_config/probe_location", EmbeddedDataType.uint8)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_config/timeout_100ns", EmbeddedDataType.uint32)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_config/trigger/condition", EmbeddedDataType.uint8, enum='SupportedTriggerConditions')
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_config/trigger/operand_count", EmbeddedDataType.uint8)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_config/trigger/hold_time_100ns", EmbeddedDataType.uint32)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_config_valid", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_encoder/m_buffer_size", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_encoder/m_reader/m_read_cursor", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_encoder/m_reader/m_finished", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_encoder/m_reader/m_read_started", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_encoder/m_max_entries", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_encoder/m_next_entry_write_index", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_encoder/m_first_valid_entry_index", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_encoder/m_entry_write_counter", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_encoder/m_entry_size", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_encoder/m_entries_count", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_encoder/m_full", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_encoder/m_error", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_decimation_counter", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_acquisition_id", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_config_id", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_log_points_after_trigger", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_trigger/previous_val", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_trigger/rising_edge_timestamp", EmbeddedDataType.uint32)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_trigger/conditions/m_data/cmt/initialized", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/threadsafe_data/datalogger_state", EmbeddedDataType.uint8, enum='DataloggerState')
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/threadsafe_data/bytes_to_acquire_from_trigger_to_completion", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/threadsafe_data/write_counter_since_trigger", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/error", EmbeddedDataType.uint8, enum='DataloggingError')
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/request_arm_trigger", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/request_ownership_release", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/request_disarm_trigger", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/pending_ownership_release", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/reading_in_progress", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/read_acquisition_rolling_counter", EmbeddedDataType.uint8)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/read_acquisition_crc", EmbeddedDataType.uint32)

    def test_scrutiny_integration(self):
        self.assert_var("/static/scrutiny_integration.cpp/rpv_write_callback(scrutiny::RuntimePublishedValue, scrutiny::AnyType const*)/some_counter", EmbeddedDataType.uint32)


    def test_bno055(self):
        self.assert_var('/global/bno055/m_i2c_addr', EmbeddedDataType.uint8)
        self.assert_var('/global/bno055/m_last_error_code', EmbeddedDataType.uint8)
        self.assert_var('/global/bno055/m_error', EmbeddedDataType.uint8, enum='Bno055DriverError')
        self.assert_var('/global/bno055/m_sys_status_at_boot', EmbeddedDataType.uint16, enum='SystemStatusCode')
        self.assert_var('/global/bno055/m_sys_error_at_boot', EmbeddedDataType.uint16, enum='SystemErrorCode')
        self.assert_var('/global/bno055/m_chip_info/acc_chip_id', EmbeddedDataType.uint8)
        self.assert_var('/global/bno055/m_chip_info/gyro_chip_id', EmbeddedDataType.uint8)
        self.assert_var('/global/bno055/m_chip_info/mag_chip_id', EmbeddedDataType.uint8)
        self.assert_var('/global/bno055/m_chip_info/sw_revision', EmbeddedDataType.uint16)
        self.assert_var('/global/bno055/m_chip_info/bootloader_version', EmbeddedDataType.uint8)
        self.assert_var('/global/bno055/m_double_buffer_flag', EmbeddedDataType.boolean)
        self.assert_var('/global/bno055/m_interrupt_read_state', EmbeddedDataType.uint8, enum='InterruptReadState')
        self.assert_var('/global/bno055/m_interrupt_read_mode', EmbeddedDataType.uint8, enum='InterruptReadMode')
        
        self.assert_var('/global/bno055/m_acc/x', EmbeddedDataType.sint16)
        self.assert_var('/global/bno055/m_acc/y', EmbeddedDataType.sint16)
        self.assert_var('/global/bno055/m_acc/z', EmbeddedDataType.sint16)
        
        self.assert_var('/global/bno055/m_gyro/x', EmbeddedDataType.sint16)
        self.assert_var('/global/bno055/m_gyro/y', EmbeddedDataType.sint16)
        self.assert_var('/global/bno055/m_gyro/z', EmbeddedDataType.sint16)
        
        self.assert_var('/global/bno055/m_mag/x', EmbeddedDataType.sint16)
        self.assert_var('/global/bno055/m_mag/y', EmbeddedDataType.sint16)
        self.assert_var('/global/bno055/m_mag/z', EmbeddedDataType.sint16)
        
        #self.assert_var('/global/bno055/m_i2c_rx_buffer', array)
        self.assert_var('/global/bno055/m_i2c_data_available', EmbeddedDataType.boolean)
        self.assert_var('/global/bno055/m_i2c_data_len', EmbeddedDataType.uint8)

if __name__ == '__main__':
    import unittest
    unittest.main()
