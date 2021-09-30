#include <gtest/gtest.h>
#include "scrutiny.h"
#include "scrutiny_test.h"

#include <iostream>

class TestGetInfo : public ::testing::Test 
{
protected:
   scrutiny::Timebase tb;
   scrutiny::MainHandler scrutiny_handler;

   TestGetInfo() {}

   virtual void SetUp() 
   {
      scrutiny::Config config; 
      config.protocol_major = 1;
      config.protocol_minor = 0;

      scrutiny_handler.init(&config);
   }
};

TEST_F(TestGetInfo, TestReadProtocolVersion) 
{
   uint8_t request_data[8] = {1,1,0,0};
   uint8_t tx_buffer[32];
   uint8_t expected_response[11] = {1,1,0,0,2,1,0};
   scrutiny_test::add_crc(request_data, 4);
   scrutiny_test::add_crc(expected_response, 7);
   scrutiny_handler.receive_data(request_data, 8);
   scrutiny_handler.process(0);
   uint32_t n_to_read = scrutiny_handler.data_to_send();
   ASSERT_GT(n_to_read, 0u);
   ASSERT_LT(n_to_read, sizeof(tx_buffer));
   EXPECT_EQ(n_to_read, sizeof(expected_response));
   
   uint32_t nread = scrutiny_handler.pop_data(tx_buffer, n_to_read);
   EXPECT_EQ(nread, n_to_read);

   ASSERT_EQ(std::memcmp( tx_buffer, expected_response, sizeof(expected_response)), 0);
}

