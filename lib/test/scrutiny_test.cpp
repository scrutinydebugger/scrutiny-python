#include <cstdint>
#include "scrutiny.h"
#include "scrutiny_test.h"

void ScrutinyTest::add_crc(uint8_t* data, uint16_t data_len)
{
	uint32_t crc = scrutiny::crc32(data, data_len);
	data[data_len] = (crc >> 24) & 0xFF;
	data[data_len + 1] = (crc >> 16) & 0xFF;
	data[data_len + 2] = (crc >> 8) & 0xFF;
	data[data_len + 3] = (crc >> 0) & 0xFF;
}

void ScrutinyTest::add_crc(scrutiny::Protocol::Response* response)
{
	uint8_t header[5];
	header[0] = response->command_id;
	header[1] = response->subfunction_id;
	header[2] = response->response_code;
	header[3] = (response->data_length >> 8) & 0xFF;
	header[4] = response->data_length & 0xFF;

	uint32_t crc = scrutiny::crc32(header, sizeof(header));
	response->crc = scrutiny::crc32(response->data, response->data_length, crc);
}

void ScrutinyTest::fill_buffer_incremental(uint8_t* buffer, uint32_t length)
{
	for (uint32_t i = 0; i < length; i++)
	{
		buffer[i] = static_cast<uint8_t>(i & 0xFFu);
	}
}

::testing::AssertionResult ScrutinyTest::COMPARE_BUF(const uint8_t* candidate, const uint8_t* expected, const uint32_t size)
{
	for (uint32_t i = 0; i < size; ++i)
	{
		if (expected[i] != candidate[i])
		{
			return ::testing::AssertionFailure() << "candidate[" << i
				<< "] (" << static_cast<uint32_t>(candidate[i]) << ") != expected[" << i
				<< "] (" << static_cast<uint32_t>(expected[i]) << ")";
		}
	}

	return ::testing::AssertionSuccess();
}

::testing::AssertionResult ScrutinyTest::IS_PROTOCOL_RESPONSE(uint8_t* buffer, scrutiny::Protocol::CommandId cmd, uint8_t subfunction, scrutiny::Protocol::ResponseCode code)
{
	if (buffer[0] != (static_cast<uint8_t>(cmd) | 0x80))
	{
		return ::testing::AssertionFailure() << "Wrong command ID. Got " << static_cast<uint32_t>(buffer[0]) << " but expected " << static_cast<uint32_t>(cmd);
	}

	if (buffer[1] != subfunction)
	{
		return ::testing::AssertionFailure() << "Wrong Subfunction. Got " << static_cast<uint32_t>(buffer[1]) << " but expected " << static_cast<uint32_t>(subfunction);
	}

	if (buffer[2] != static_cast<uint8_t>(code))
	{
		return ::testing::AssertionFailure() << "Wrong response code. Got " << static_cast<uint32_t>(buffer[2]) << " but expected " << static_cast<uint32_t>(code);
	}
	uint16_t length = (static_cast<uint16_t>(buffer[3]) << 8) | static_cast<uint16_t>(buffer[4]);
	if (code != scrutiny::Protocol::eResponseCode_OK && length != 0)
	{
		return ::testing::AssertionFailure() << "Wrong command length. Got " << static_cast<uint32_t>(length) << " but expected 0";
	}


	return ::testing::AssertionSuccess();
}

#if defined(_MSC_VER)
	#pragma warning(push)
	#pragma warning(disable:4293)   // Get rid of shift to big warning.
#endif 

unsigned int ScrutinyTest::encode_addr(uint8_t* buffer, void* addr)
{
	unsigned int i = 0;
	std::uintptr_t ptr = reinterpret_cast<std::uintptr_t>(addr);
	switch (sizeof(ptr))
	{
	case 8:
		buffer[i++] = static_cast<uint8_t>((ptr >> 56));
		buffer[i++] = static_cast<uint8_t>((ptr >> 48));
		buffer[i++] = static_cast<uint8_t>((ptr >> 40));
		buffer[i++] = static_cast<uint8_t>((ptr >> 32));
	case 4:
		buffer[i++] = static_cast<uint8_t>((ptr >> 24));
		buffer[i++] = static_cast<uint8_t>((ptr >> 16));
	case 2:
		buffer[i++] = static_cast<uint8_t>((ptr >> 8));
	case 1:
		buffer[i++] = static_cast<uint8_t>((ptr >> 0));
	default:
		break;
	}

	return i;
}

#if defined(_MSC_VER)
	#pragma warning(pop)
#endif 




