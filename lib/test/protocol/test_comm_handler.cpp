//    test_comm_handler.cpp
//        Test the tranport-ish layer good behaviour at high level.
//
//   - License : MIT - See LICENSE file.
//   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
//
//   Copyright (c) 2021-2022 scrutinydebugger

#include <gtest/gtest.h>
#include <cstring>

#include "scrutiny.h"
#include "scrutiny_test.h"


class TestCommHandler : public ScrutinyTest
{
protected:
	scrutiny::Timebase tb;
	scrutiny::protocol::CommHandler comm;
	uint8_t response_buffer[256];
	scrutiny::protocol::Response response;

	virtual void SetUp()
	{
		comm.init(&tb);
		response.data = response_buffer;
	}
};


TEST_F(TestCommHandler, TestConsecutiveSend)
{
	uint8_t buf[256];

	response.command_id = 0x81;
	response.subfunction_id = 0x02;
	response.response_code = 0x03;
	response.data_length = 3;
	response.data[0] = 0x11;
	response.data[1] = 0x22;
	response.data[2] = 0x33;

	add_crc(&response);
	uint8_t expected_data[12] = { 0x81,2,3,0,3,0x11, 0x22, 0x33 };
	add_crc(expected_data, 8);

	bool success;
	EXPECT_FALSE(comm.transmitting());
	success = comm.send_response(&response);
	EXPECT_TRUE(success);
	EXPECT_TRUE(comm.transmitting());
	success = comm.send_response(&response);   // This one should be ignored
	EXPECT_FALSE(success);

	uint32_t n_to_read = comm.data_to_send();
	ASSERT_GT(n_to_read, 0u);
	ASSERT_LT(n_to_read, sizeof(buf));
	EXPECT_EQ(n_to_read, sizeof(expected_data));

	comm.pop_data(buf, n_to_read);
	ASSERT_EQ(std::memcmp(buf, expected_data, sizeof(expected_data)), 0);
	std::memset(buf, 0, sizeof(buf));   // clear last message received
	EXPECT_EQ(comm.data_to_send(), 0u);
	EXPECT_FALSE(comm.transmitting());

	success = comm.send_response(&response);
	EXPECT_TRUE(success);
	EXPECT_TRUE(comm.transmitting());

	n_to_read = comm.data_to_send();
	ASSERT_GT(n_to_read, 0u);
	ASSERT_LT(n_to_read, sizeof(buf));
	EXPECT_EQ(n_to_read, sizeof(expected_data));

	comm.pop_data(buf, n_to_read);
	ASSERT_EQ(std::memcmp(buf, expected_data, sizeof(expected_data)), 0);
}

TEST_F(TestCommHandler, TestHeartbeatTimeoutExpire)
{
	ASSERT_FALSE(comm.is_connected());
	comm.connect();
	ASSERT_TRUE(comm.is_connected());
	tb.step(SCRUTINY_COMM_HEARTBEAT_TMEOUT_US - 1);
	comm.process();
	ASSERT_TRUE(comm.is_connected());
	comm.heartbeat(10); // first rolling counter always valid
	tb.step(SCRUTINY_COMM_HEARTBEAT_TMEOUT_US - 1);
	comm.process();
	ASSERT_TRUE(comm.is_connected());
	tb.step(SCRUTINY_COMM_HEARTBEAT_TMEOUT_US - 1);
	comm.heartbeat(11);
	comm.process();
	ASSERT_TRUE(comm.is_connected());
	tb.step(SCRUTINY_COMM_HEARTBEAT_TMEOUT_US - 1);
	comm.heartbeat(11);  // Will be ignored since rolling_counter didn't change.
	comm.process();
	ASSERT_TRUE(comm.is_connected());
	tb.step(1);
	comm.process();
	ASSERT_FALSE(comm.is_connected());
}

TEST_F(TestCommHandler, TestConnectDisconnectBehaviour)
{
	uint32_t session_id;
	ASSERT_FALSE(comm.is_connected());
	comm.connect();
	ASSERT_TRUE(comm.is_connected());
	session_id = comm.get_session_id();
	comm.disconnect();
	ASSERT_FALSE(comm.is_connected());
	comm.connect();
	ASSERT_NE(comm.get_session_id(), session_id);

	uint8_t dummy_request[8] = { 1,1,0,0 };
	add_crc(dummy_request, sizeof(dummy_request) - 4);
	
	EXPECT_FALSE(comm.request_received());
	comm.receive_data(dummy_request, sizeof(dummy_request));
	comm.process();
	EXPECT_TRUE(comm.request_received());
	comm.disconnect();
	EXPECT_FALSE(comm.request_received());

	comm.connect();
	comm.receive_data(dummy_request, sizeof(dummy_request)-1);
	comm.process();
	EXPECT_FALSE(comm.request_received());
	comm.disconnect();
	comm.connect();
	comm.receive_data(&dummy_request[sizeof(dummy_request)-1], 1);
	EXPECT_FALSE(comm.request_received());
}