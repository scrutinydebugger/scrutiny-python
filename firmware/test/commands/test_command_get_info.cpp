#include <gtest/gtest.h>
#include <cstring>

#include "scrutiny.h"
#include "scrutiny_test.h"

class TestGetInfo : public ScrutinyTest
{
protected:
   scrutiny::Timebase tb;
   scrutiny::MainHandler scrutiny_handler;

   TestGetInfo() {}

   virtual void SetUp() 
   {
      scrutiny::Config config;
      scrutiny_handler.init(&config);
      scrutiny_handler.enable_comm();
   }
};

TEST_F(TestGetInfo, TestReadProtocolVersion) 
{
   uint8_t request_data[8] = {1,1,0,0};
   uint8_t tx_buffer[32];
   uint8_t expected_response[11] = {0x81,1,0,0,2,1,0};   // Version 1.0
   add_crc(request_data, 4);
   add_crc(expected_response, 7);
   scrutiny_handler.receive_data(request_data, 8);
   scrutiny_handler.process(0);
   uint32_t n_to_read = scrutiny_handler.data_to_send();
   ASSERT_GT(n_to_read, 0u);
   ASSERT_LT(n_to_read, sizeof(tx_buffer));
   EXPECT_EQ(n_to_read, sizeof(expected_response));
   
   uint32_t nread = scrutiny_handler.pop_data(tx_buffer, n_to_read);
   EXPECT_EQ(nread, n_to_read);

   ASSERT_BUF_EQ(tx_buffer, expected_response, sizeof(expected_response));
}


TEST_F(TestGetInfo, TestReadSoftwareId) 
{
   EXPECT_EQ(sizeof(scrutiny::software_id), SOFTWARE_ID_LENGTH);
   uint8_t tx_buffer[SOFTWARE_ID_LENGTH+32];

   // Make request
   uint8_t request_data[8 + SOFTWARE_ID_LENGTH] = {1,2,0,0};
   request_data[2] = (SOFTWARE_ID_LENGTH >> 8) & 0xFF;
   request_data[3] = SOFTWARE_ID_LENGTH & 0xFF;
   std::memcpy(&request_data[4], scrutiny::software_id, SOFTWARE_ID_LENGTH);
   add_crc(request_data, 4+SOFTWARE_ID_LENGTH);
   
   // Make expected response
   uint8_t expected_response[9+SOFTWARE_ID_LENGTH] = {0x81,2,0};
   expected_response[3] = (SOFTWARE_ID_LENGTH >> 8) & 0xFF;
   expected_response[4] = SOFTWARE_ID_LENGTH & 0xFF;
   std::memcpy(&expected_response[5], scrutiny::software_id, SOFTWARE_ID_LENGTH);
   add_crc(expected_response, 5+SOFTWARE_ID_LENGTH);

   scrutiny_handler.receive_data(request_data, sizeof(request_data));
   scrutiny_handler.process(0);

   uint32_t n_to_read = scrutiny_handler.data_to_send();
   ASSERT_GT(n_to_read, 0u);
   ASSERT_LT(n_to_read, sizeof(tx_buffer));
   EXPECT_EQ(n_to_read, sizeof(expected_response));
   
   uint32_t nread = scrutiny_handler.pop_data(tx_buffer, n_to_read);
   EXPECT_EQ(nread, n_to_read);
   ASSERT_BUF_EQ( tx_buffer, expected_response, sizeof(expected_response));
}
