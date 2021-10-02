#include <cstdint>
#include "scrutiny.h"
#include "scrutiny_test.h"

void ScrutinyTest::add_crc(uint8_t* data, uint16_t data_len)
{
    uint32_t crc = scrutiny::crc32(data, data_len);
    data[data_len] = (crc >> 24) & 0xFF;
    data[data_len+1] = (crc >> 16) & 0xFF;
    data[data_len+2] = (crc >> 8) & 0xFF;
    data[data_len+3] = (crc >> 0) & 0xFF;
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

::testing::AssertionResult ScrutinyTest::COMPARE_BUF( const uint8_t* candidate, const uint8_t* expected, const uint32_t size)
{
    for (uint32_t i=0; i < size; ++i)
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

