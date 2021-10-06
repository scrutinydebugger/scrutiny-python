#include <gtest/gtest.h>
#include <cstring>

#include "scrutiny.h"
#include "scrutiny_test.h"

class TestCommControl : public ScrutinyTest
{
protected:
	scrutiny::Timebase tb;
	scrutiny::MainHandler scrutiny_handler;
	scrutiny::Config config;

	virtual void SetUp()
	{
		config.set_max_bitrate(0x12345678);
		scrutiny_handler.init(&config);
	}
};


TEST_F(TestCommControl, TestDiscover)
{
	ASSERT_FALSE(scrutiny_handler.comm()->is_connected());   // We should get a Discover response even when not connected.
	ASSERT_EQ(sizeof(scrutiny::Protocol::CommControl::DISCOVER_MAGIC), 4u);
	const uint8_t challenge[4] = { 0x11, 0x22, 0x33, 0x44 };
	const uint8_t challenge_response[4] = { 0xEE, 0xDD, 0xCC, 0xBB };
	uint8_t request_data[8 + 4 + 4] = { 2,1,0,8 };
	std::memcpy(&request_data[4], scrutiny::Protocol::CommControl::DISCOVER_MAGIC, sizeof(scrutiny::Protocol::CommControl::DISCOVER_MAGIC));
	std::memcpy(&request_data[8], challenge, sizeof(challenge));


	uint8_t tx_buffer[32];
	uint8_t expected_response[9 + 4 + 4] = { 0x82,1,0,0,8 };   // Version 1.0
	std::memcpy(&expected_response[5], scrutiny::Protocol::CommControl::DISCOVER_MAGIC, sizeof(scrutiny::Protocol::CommControl::DISCOVER_MAGIC));
	std::memcpy(&expected_response[9], challenge_response, sizeof(challenge_response));

	add_crc(request_data, sizeof(request_data) - 4);
	add_crc(expected_response, sizeof(expected_response) - 4);

	scrutiny_handler.comm()->receive_data(request_data, sizeof(request_data));
	scrutiny_handler.process(0);
	uint32_t n_to_read = scrutiny_handler.comm()->data_to_send();
	ASSERT_GT(n_to_read, 0u);
	ASSERT_LT(n_to_read, sizeof(tx_buffer));
	EXPECT_EQ(n_to_read, sizeof(expected_response));

	uint32_t nread = scrutiny_handler.comm()->pop_data(tx_buffer, n_to_read);
	EXPECT_EQ(nread, n_to_read);

	ASSERT_BUF_EQ(tx_buffer, expected_response, sizeof(expected_response));
}


TEST_F(TestCommControl, TestHeartbeat)
{
	uint8_t request_data[8 + 4 + 2] = { 2,2,0,6 };

	uint8_t tx_buffer[32];
	uint8_t expected_response[9 + 4 + 2] = { 0x82,2,0,0,6 };

	scrutiny_handler.comm()->connect();
	uint32_t session_id = scrutiny_handler.comm()->get_session_id();
	request_data[4] = (session_id >> 24) & 0xFF;
	request_data[5] = (session_id >> 16) & 0xFF;
	request_data[6] = (session_id >> 8) & 0xFF;
	request_data[7] = (session_id >> 0) & 0xFF;

	expected_response[5] = (session_id >> 24) & 0xFF;
	expected_response[6] = (session_id >> 16) & 0xFF;
	expected_response[7] = (session_id >> 8) & 0xFF;
	expected_response[8] = (session_id >> 0) & 0xFF;

	// So we expect the comm to stay enabled after multiple call to heartbeat even if time goes by
	for (uint16_t challenge = 0; challenge < 4; challenge++)
	{
		request_data[8] = ((challenge >> 8) & 0xFF);
		request_data[9] = (challenge & 0xFF);
		expected_response[9] = ~request_data[8];
		expected_response[10] = ~request_data[9];
		ASSERT_TRUE(scrutiny_handler.comm()->is_connected()) << "challenge=" << static_cast<uint32_t>(challenge);

		add_crc(request_data, sizeof(request_data) - 4);
		add_crc(expected_response, sizeof(expected_response) - 4);
		scrutiny_handler.comm()->receive_data(request_data, sizeof(request_data));
		scrutiny_handler.process(SCRUTINY_COMM_HEARTBEAT_TMEOUT_US / 2);

		uint32_t n_to_read = scrutiny_handler.comm()->data_to_send();
		ASSERT_EQ(n_to_read, sizeof(expected_response)) << "challenge=" << static_cast<uint32_t>(challenge);
		uint32_t nread = scrutiny_handler.comm()->pop_data(tx_buffer, n_to_read);
		EXPECT_EQ(nread, n_to_read) << "challenge=" << static_cast<uint32_t>(challenge);

		ASSERT_BUF_EQ(tx_buffer, expected_response, sizeof(expected_response)) << "challenge=" << static_cast<uint32_t>(challenge);
		ASSERT_TRUE(scrutiny_handler.comm()->is_connected()) << "challenge=" << static_cast<uint32_t>(challenge);
		scrutiny_handler.process(0);
	}
}

TEST_F(TestCommControl, TestGetParams)
{
	uint8_t tx_buffer[32];
	uint8_t request_data[8] = { 2,3,0,0 };
	add_crc(request_data, sizeof(request_data) - 4);

	uint8_t expected_response[9 + 2 + 4 + 4 + 4] = { 0x82,3,0,0,14 };
	uint8_t i = 5;
	expected_response[i++] = (SCRUTINY_BUFFER_SIZE >> 8) & 0xFF;
	expected_response[i++] = (SCRUTINY_BUFFER_SIZE) & 0xFF;
	expected_response[i++] = (config.get_max_bitrate() >> 24) & 0xFF;
	expected_response[i++] = (config.get_max_bitrate() >> 16) & 0xFF;
	expected_response[i++] = (config.get_max_bitrate() >> 8) & 0xFF;
	expected_response[i++] = (config.get_max_bitrate() >> 0) & 0xFF;
	expected_response[i++] = (SCRUTINY_COMM_HEARTBEAT_TMEOUT_US >> 24) & 0xFF;
	expected_response[i++] = (SCRUTINY_COMM_HEARTBEAT_TMEOUT_US >> 16) & 0xFF;
	expected_response[i++] = (SCRUTINY_COMM_HEARTBEAT_TMEOUT_US >> 8) & 0xFF;
	expected_response[i++] = (SCRUTINY_COMM_HEARTBEAT_TMEOUT_US >> 0) & 0xFF;
	expected_response[i++] = (SCRUTINY_COMM_RX_TIMEOUT_US >> 24) & 0xFF;
	expected_response[i++] = (SCRUTINY_COMM_RX_TIMEOUT_US >> 16) & 0xFF;
	expected_response[i++] = (SCRUTINY_COMM_RX_TIMEOUT_US >> 8) & 0xFF;
	expected_response[i++] = (SCRUTINY_COMM_RX_TIMEOUT_US >> 0) & 0xFF;
	add_crc(expected_response, sizeof(expected_response) - 4);

	scrutiny_handler.comm()->connect();
	scrutiny_handler.comm()->receive_data(request_data, sizeof(request_data));
	scrutiny_handler.process(0);
	uint32_t n_to_read = scrutiny_handler.comm()->data_to_send();
	ASSERT_GT(n_to_read, 0u);
	ASSERT_LT(n_to_read, sizeof(tx_buffer));
	EXPECT_EQ(n_to_read, sizeof(expected_response));

	uint32_t nread = scrutiny_handler.comm()->pop_data(tx_buffer, n_to_read);
	EXPECT_EQ(nread, n_to_read);

	ASSERT_BUF_EQ(tx_buffer, expected_response, sizeof(expected_response));
}


TEST_F(TestCommControl, TestConnect)
{
	ASSERT_EQ(sizeof(scrutiny::Protocol::CommControl::CONNECT_MAGIC), 4u);
	uint8_t request_data[8 + 4] = { 2,4,0,4 };
	std::memcpy(&request_data[4], scrutiny::Protocol::CommControl::CONNECT_MAGIC, sizeof(scrutiny::Protocol::CommControl::CONNECT_MAGIC));

	uint8_t tx_buffer[32];
	uint8_t expected_response[9 + 4 + 4] = { 0x82,4,0,0,8 };   // Version 1.0
	std::memcpy(&expected_response[5], scrutiny::Protocol::CommControl::CONNECT_MAGIC, sizeof(scrutiny::Protocol::CommControl::CONNECT_MAGIC));

	add_crc(request_data, sizeof(request_data) - 4);


	ASSERT_FALSE(scrutiny_handler.comm()->is_connected());
	scrutiny_handler.comm()->receive_data(request_data, sizeof(request_data));
	scrutiny_handler.process(0);

	uint32_t n_to_read = scrutiny_handler.comm()->data_to_send();
	ASSERT_GT(n_to_read, 0u);
	ASSERT_LT(n_to_read, sizeof(tx_buffer));
	EXPECT_EQ(n_to_read, sizeof(expected_response));

	uint32_t nread = scrutiny_handler.comm()->pop_data(tx_buffer, n_to_read);
	EXPECT_EQ(nread, n_to_read);

	uint32_t session_id = scrutiny_handler.comm()->get_session_id();

	expected_response[9] = (session_id >> 24) & 0xFF;
	expected_response[10] = (session_id >> 16) & 0xFF;
	expected_response[11] = (session_id >> 8) & 0xFF;
	expected_response[12] = (session_id >> 0) & 0xFF;
	add_crc(expected_response, sizeof(expected_response) - 4);

	ASSERT_BUF_EQ(tx_buffer, expected_response, sizeof(expected_response));
	ASSERT_TRUE(scrutiny_handler.comm()->is_connected());
}


TEST_F(TestCommControl, TestDisconnect)
{
	scrutiny_handler.comm()->connect();
	uint32_t session_id = scrutiny_handler.comm()->get_session_id();
	uint8_t request_data[8 + 4] = { 2,5,0,4 };
	request_data[4] = (session_id >> 24) & 0xFF;
	request_data[5] = (session_id >> 16) & 0xFF;
	request_data[6] = (session_id >> 8) & 0xFF;
	request_data[7] = (session_id >> 0) & 0xFF;
	add_crc(request_data, sizeof(request_data) - 4);

	uint8_t tx_buffer[32];
	uint8_t expected_response[9] = { 0x82,5,0,0,0 };   // Version 1.0
	add_crc(expected_response, sizeof(expected_response) - 4);

	ASSERT_TRUE(scrutiny_handler.comm()->is_connected());
	scrutiny_handler.comm()->receive_data(request_data, sizeof(request_data));
	scrutiny_handler.process(0);

	uint32_t n_to_read = scrutiny_handler.comm()->data_to_send();
	ASSERT_GT(n_to_read, 0u);
	ASSERT_LT(n_to_read, sizeof(tx_buffer));
	EXPECT_EQ(n_to_read, sizeof(expected_response));

	uint32_t nread = scrutiny_handler.comm()->pop_data(tx_buffer, n_to_read);
	EXPECT_EQ(nread, n_to_read);
	scrutiny_handler.process(0);  // We need a subsequent call to process because disconnection hapens once the response is completely sent.

	ASSERT_BUF_EQ(tx_buffer, expected_response, sizeof(expected_response));
	ASSERT_FALSE(scrutiny_handler.comm()->is_connected());
}