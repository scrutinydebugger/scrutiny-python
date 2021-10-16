#include <gtest/gtest.h>
#include <cstring>

#include "scrutiny.h"
#include "scrutiny_test.h"


class TestUserCommand : public ScrutinyTest
{
protected:
	scrutiny::Timebase tb;
	scrutiny::MainHandler scrutiny_handler;
	scrutiny::Config config;
};


void my_callback1(const uint8_t subfunction, const uint8_t* request_data, const uint16_t request_data_length, uint8_t* response_data, uint16_t* response_data_length, const uint16_t response_max_data_length)
{
	EXPECT_EQ(subfunction, 0xAA);
	EXPECT_EQ(request_data_length, 0x3);
	EXPECT_EQ(request_data[0], 0x12);
	EXPECT_EQ(request_data[1], 0x34);
	EXPECT_EQ(request_data[2], 0x56);

	EXPECT_EQ(response_max_data_length, SCRUTINY_TX_BUFFER_SIZE);

	response_data[0] = 0x11;
	response_data[1] = 0x22;
	response_data[2] = 0x33;
	response_data[3] = 0x44;

	*response_data_length = 4;
}

#if defined(_MSC_VER)
	#pragma warning(push)
	#pragma warning(disable:4100)   // Get rid of unused parameter warning.
#endif 

void my_callback2(const uint8_t subfunction, const uint8_t* request_data, const uint16_t request_data_length, uint8_t* response_data, uint16_t* response_data_length, const uint16_t response_max_data_length)
{
	*response_data_length = response_max_data_length+1;
}

#if defined(_MSC_VER)
	#pragma warning(pop)
#endif 


TEST_F(TestUserCommand, TestCommandCalled)
{
	uint8_t tx_buffer[32];
	config.user_command_callback = &my_callback1;
	scrutiny_handler.init(&config);
	scrutiny_handler.comm()->connect();

	uint8_t request_data[8 + 3] = { 5, 0xAA, 0, 3, 0x12, 0x34, 0x56 };
	add_crc(request_data, sizeof(request_data) - 4);

	uint8_t expected_response[9 + 4] = { 0x85, 0xAA, 0,  0, 4, 0x11, 0x22, 0x33, 0x44 };
	add_crc(expected_response, sizeof(expected_response) - 4);

	scrutiny_handler.comm()->receive_data(request_data, sizeof(request_data));
	scrutiny_handler.process(0);

	uint32_t n_to_read = scrutiny_handler.comm()->data_to_send();
	ASSERT_EQ(n_to_read, sizeof(expected_response));

	scrutiny_handler.comm()->pop_data(tx_buffer, n_to_read);
	COMPARE_BUF(tx_buffer, expected_response, sizeof(expected_response));
}

TEST_F(TestUserCommand, TestResponseOverflow)
{
	const scrutiny::Protocol::CommandId cmd = scrutiny::Protocol::eCmdUserCommand;
	const scrutiny::Protocol::ResponseCode code = scrutiny::Protocol::eResponseCode_Overflow;

	uint8_t tx_buffer[32];
	config.user_command_callback = &my_callback2;
	scrutiny_handler.init(&config);
	scrutiny_handler.comm()->connect();

	uint8_t request_data[8] = { 5, 0, 0, 0 };
	add_crc(request_data, sizeof(request_data) - 4);

	scrutiny_handler.comm()->receive_data(request_data, sizeof(request_data));
	scrutiny_handler.process(0);

	uint32_t n_to_read = scrutiny_handler.comm()->data_to_send();

	scrutiny_handler.comm()->pop_data(tx_buffer, n_to_read);
	ASSERT_TRUE(IS_PROTOCOL_RESPONSE(tx_buffer, cmd, 0, code));
}

TEST_F(TestUserCommand, TestNoCallback)
{
	const scrutiny::Protocol::CommandId cmd = scrutiny::Protocol::eCmdUserCommand;
	const scrutiny::Protocol::ResponseCode code = scrutiny::Protocol::eResponseCode_UnsupportedFeature;

	uint8_t tx_buffer[32];
	// No callback set on purpose
	scrutiny_handler.init(&config);
	scrutiny_handler.comm()->connect();

	uint8_t request_data[8] = { 5, 0, 0, 0 };
	add_crc(request_data, sizeof(request_data) - 4);

	scrutiny_handler.comm()->receive_data(request_data, sizeof(request_data));
	scrutiny_handler.process(0);

	uint32_t n_to_read = scrutiny_handler.comm()->data_to_send();

	scrutiny_handler.comm()->pop_data(tx_buffer, n_to_read);
	ASSERT_TRUE(IS_PROTOCOL_RESPONSE(tx_buffer, cmd, 0, code));
}