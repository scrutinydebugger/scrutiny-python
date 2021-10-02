#include <gtest/gtest.h>

#include "scrutiny.h"
#include "scrutiny_test.h"


class TestCommHandler : public ScrutinyTest
{
protected:
   scrutiny::Timebase tb;
   scrutiny::Protocol::CommHandler comm;
   uint8_t response_buffer[256];
   scrutiny::Protocol::Response response;

   TestCommHandler() {}

   virtual void SetUp() 
   {
      comm.init(&tb);
      response.data = response_buffer;
      comm.set_enabled();
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
   response.valid = true;
   
   add_crc(&response);
   uint8_t expected_data[12] = {0x81,2,3,0,3,0x11, 0x22, 0x33};
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
   ASSERT_EQ(std::memcmp( buf, expected_data, sizeof(expected_data)), 0);
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
   ASSERT_EQ(std::memcmp( buf, expected_data, sizeof(expected_data)), 0);
}