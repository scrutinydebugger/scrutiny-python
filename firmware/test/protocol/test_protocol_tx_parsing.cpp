#include <gtest/gtest.h>

#include "scrutiny.h"
#include "scrutiny_test.h"


class TestTxParsing : public ScrutinyTest
{
protected:
   scrutiny::Timebase tb;
   scrutiny::Protocol::CommHandler comm;
   uint8_t response_buffer[256];
   scrutiny::Protocol::Response response;

   TestTxParsing() {}

   virtual void SetUp() 
   {
      comm.init(&tb);
      response.data = response_buffer;
      comm.set_enabled();
   }
};

TEST_F(TestTxParsing, TestReadAllData) 
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

   comm.send_response(&response);
   
   uint8_t expected_data[12] = {0x81,2,3,0,3,0x11, 0x22, 0x33};
   add_crc(expected_data, 8);
   
   uint32_t n_to_read = comm.data_to_send();
   ASSERT_GT(n_to_read, 0u);
   ASSERT_LT(n_to_read, sizeof(buf));
   EXPECT_EQ(n_to_read, sizeof(expected_data));
   
   uint32_t nread = comm.pop_data(buf, n_to_read);
   EXPECT_EQ(nread, n_to_read);

   ASSERT_EQ(std::memcmp( buf, expected_data, sizeof(expected_data)), 0);
}


TEST_F(TestTxParsing, TestReadBytePerByte) 
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

   comm.send_response(&response);
   
   uint8_t expected_data[12] = {0x81,2,3,0,3,0x11, 0x22, 0x33};
   add_crc(expected_data, 8);
   
   uint32_t n_to_read = comm.data_to_send();
   ASSERT_GT(n_to_read, 0u);
   ASSERT_LT(n_to_read, sizeof(buf));
   EXPECT_EQ(n_to_read, sizeof(expected_data));
   
   uint32_t nread;
   for (uint32_t i=0; i<n_to_read; i++)
   {
      nread = comm.pop_data(&buf[i], 1);
      EXPECT_EQ(nread, 1u);
   }

   ASSERT_EQ(std::memcmp( buf, expected_data, sizeof(expected_data)), 0);
}

TEST_F(TestTxParsing, TestReadByChunk) 
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

   comm.send_response(&response);
   
   uint8_t expected_data[12] = {0x81,2,3,0,3,0x11, 0x22, 0x33};
   add_crc(expected_data, 8);
   
   uint32_t n_to_read = comm.data_to_send();
   uint8_t chunks[3] = {3,6,3};
   ASSERT_EQ(n_to_read, 12u);

   uint32_t nread;
   uint8_t index=0;
   for (uint32_t i=0; i<sizeof(chunks); i++)
   {
      nread = comm.pop_data(&buf[index], chunks[i]);
      EXPECT_EQ(nread, static_cast<uint32_t>(chunks[i]));
      index += chunks[i];
   }

   ASSERT_EQ(std::memcmp( buf, expected_data, sizeof(expected_data)), 0);
}

TEST_F(TestTxParsing, TestReadMoreThanAvailable) 
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

   comm.send_response(&response);
   
   uint8_t expected_data[12] = {0x81,2,3,0,3,0x11, 0x22, 0x33};
   add_crc(expected_data, 8);
   
   uint32_t n_to_read = comm.data_to_send();
   uint32_t nread = comm.pop_data(buf, n_to_read+10);
   EXPECT_EQ(nread, n_to_read);

   ASSERT_EQ(std::memcmp( buf, expected_data, sizeof(expected_data)), 0);
}

