#include <gtest/gtest.h>
#include "scrutiny.h"
#include "scrutiny_test.h"

class TestCommControl : public ScrutinyTest
{
protected:
   scrutiny::Timebase tb;
   scrutiny::MainHandler scrutiny_handler;

   TestCommControl() {}

   virtual void SetUp() 
   {
      scrutiny_handler.init();
   }
};

TEST_F(TestCommControl, TestDiscover) 
{
   ASSERT_EQ(sizeof(scrutiny::Protocol::CommControl::DISCOVER_MAGIC), 4);
   const uint8_t challenge[4] = {0x11, 0x22, 0x33, 0x44};
   const uint8_t challenge_response[4] = {0xEE, 0xDD, 0xCC, 0xBB};
   uint8_t request_data[8+4+4] = {2,1,0,8};
   std::memcpy(&request_data[4], scrutiny::Protocol::CommControl::DISCOVER_MAGIC, sizeof(scrutiny::Protocol::CommControl::DISCOVER_MAGIC));
   std::memcpy(&request_data[8], challenge, sizeof(challenge));
   

   uint8_t tx_buffer[32];
   uint8_t expected_response[9+4+4] = {0x82,1,0,0,8};   // Version 1.0
   std::memcpy(&expected_response[5], scrutiny::Protocol::CommControl::DISCOVER_MAGIC, sizeof(scrutiny::Protocol::CommControl::DISCOVER_MAGIC));
   std::memcpy(&expected_response[9], challenge_response, sizeof(challenge_response));

   add_crc(request_data, sizeof(request_data)-4);
   add_crc(expected_response, sizeof(expected_response)-4);

   EXPECT_FALSE(scrutiny_handler.comm_enabled());
   scrutiny_handler.receive_data(request_data, sizeof(request_data));
   scrutiny_handler.process(0);
   EXPECT_TRUE(scrutiny_handler.comm_enabled());
   uint32_t n_to_read = scrutiny_handler.data_to_send();
   ASSERT_GT(n_to_read, 0u);
   ASSERT_LT(n_to_read, sizeof(tx_buffer));
   EXPECT_EQ(n_to_read, sizeof(expected_response));
   
   uint32_t nread = scrutiny_handler.pop_data(tx_buffer, n_to_read);
   EXPECT_EQ(nread, n_to_read);

   ASSERT_BUF_EQ( tx_buffer, expected_response, sizeof(expected_response));
}


TEST_F(TestCommControl, TestHeartbeat) 
{
   scrutiny_handler.enable_comm();  // Enable comm without a Discover command
   uint8_t request_data[8+2] = {2,2,0,2};
   
   uint8_t tx_buffer[32];
   uint8_t expected_response[9+2] = {0x82,2,0,0,2};   // Version 1.0

   // So we expect the comm to stay enabled after multiple call to heartbeat even if time goes by
   for (uint16_t challenge=0; challenge<4; challenge++)
   {
      request_data[4] = ((challenge>>8) & 0xFF);
      request_data[5] = (challenge & 0xFF);
      expected_response[5] = ~request_data[4];
      expected_response[6] = ~request_data[5];
      ASSERT_TRUE(scrutiny_handler.comm_enabled())                            << "challenge=" << static_cast<uint32_t>(challenge);

      add_crc(request_data, sizeof(request_data)-4);
      add_crc(expected_response, sizeof(expected_response)-4);
      scrutiny_handler.receive_data(request_data, sizeof(request_data));
      scrutiny_handler.process(SCRUTINY_COMM_HEARTBEAT_TMEOUT_US/2);

      uint32_t n_to_read = scrutiny_handler.data_to_send();
      ASSERT_EQ(n_to_read, sizeof(expected_response))                         << "challenge=" << static_cast<uint32_t>(challenge);
      uint32_t nread = scrutiny_handler.pop_data(tx_buffer, n_to_read);
      EXPECT_EQ(nread, n_to_read)                                             << "challenge=" << static_cast<uint32_t>(challenge);

      ASSERT_BUF_EQ( tx_buffer, expected_response, sizeof(expected_response)) << "challenge=" << static_cast<uint32_t>(challenge);
      ASSERT_TRUE(scrutiny_handler.comm_enabled())                            << "challenge=" << static_cast<uint32_t>(challenge);
      scrutiny_handler.process(0);
   }
}
