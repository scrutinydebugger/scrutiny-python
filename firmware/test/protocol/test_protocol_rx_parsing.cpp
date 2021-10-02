#include <gtest/gtest.h>

#include "scrutiny.h"
#include "scrutiny_test.h"

class TestRxParsing : public ScrutinyTest
{
protected:
   scrutiny::Timebase tb;
   scrutiny::Protocol::CommHandler comm;

   TestRxParsing() {}

   virtual void SetUp() 
   {
      comm.init(&tb);
      comm.set_enabled();
   }
};

//=============================================================================
TEST_F(TestRxParsing, TestRx_ZeroLen_AllInOne)
{
  uint8_t data[8] = {1,2,0,0};
  add_crc(data, 4);
  comm.process_data(data, sizeof(data));

  ASSERT_TRUE(comm.request_received());
  scrutiny::Protocol::Request* req = comm.get_request();
  EXPECT_EQ(req->command_id, 1);
  EXPECT_EQ(req->subfunction_id, 2);
  EXPECT_EQ(req->data_length, 0);
  
  EXPECT_EQ(comm.get_rx_error(), scrutiny::Protocol::eRxErrorNone);
}

//=============================================================================
TEST_F(TestRxParsing, TestRx_ZeroLen_BytePerByte)
{
  uint8_t data[8] = {1,2,0,0};
  add_crc(data, 4);

  for (unsigned int i=0; i<sizeof(data); i++)
  {
    comm.process_data(&data[i], 1);
  }

  ASSERT_TRUE(comm.request_received());
  scrutiny::Protocol::Request* req = comm.get_request();
  EXPECT_EQ(req->command_id, 1);
  EXPECT_EQ(req->subfunction_id, 2);
  EXPECT_EQ(req->data_length, 0);

  EXPECT_EQ(comm.get_rx_error(), scrutiny::Protocol::eRxErrorNone);
}

//=============================================================================
TEST_F(TestRxParsing, TestRx_NonZeroLen_AllInOne)
{
  uint8_t data[11] = {1,2,0,3, 0x11, 0x22, 0x33};
  add_crc(data, 7);
  comm.process_data(data, sizeof(data));

  ASSERT_TRUE(comm.request_received());
  scrutiny::Protocol::Request* req = comm.get_request();
  EXPECT_EQ(req->command_id, 1);
  EXPECT_EQ(req->subfunction_id, 2);
  EXPECT_EQ(req->data_length, 3);
  EXPECT_EQ(req->data[0], 0x11);
  EXPECT_EQ(req->data[1], 0x22);
  EXPECT_EQ(req->data[2], 0x33);
  
  EXPECT_EQ(comm.get_rx_error(), scrutiny::Protocol::eRxErrorNone);
}

//=============================================================================
TEST_F(TestRxParsing, TestRx_NonZeroLen_BytePerByte)
{
  uint8_t data[11] = {1,2,0,3, 0x11, 0x22, 0x33};
  add_crc(data, 7);

  for (unsigned int i=0; i<sizeof(data); i++)
  {
    comm.process_data(&data[i], 1);
  }

  ASSERT_TRUE(comm.request_received());
  scrutiny::Protocol::Request* req = comm.get_request();
  EXPECT_EQ(req->command_id, 1);
  EXPECT_EQ(req->subfunction_id, 2);
  EXPECT_EQ(req->data_length, 3);
  EXPECT_EQ(req->data[0], 0x11);
  EXPECT_EQ(req->data[1], 0x22);
  EXPECT_EQ(req->data[2], 0x33);
  
  EXPECT_EQ(comm.get_rx_error(), scrutiny::Protocol::eRxErrorNone);
}

//=============================================================================
TEST_F(TestRxParsing, TestRx_Overflow)
{
  ASSERT_LT(SCRUTINY_BUFFER_SIZE, 0xFFFFu-1u);  // Lengths are 16bits maximum by protocol definition

  uint16_t datalen = SCRUTINY_BUFFER_SIZE + 1;

  uint8_t data[SCRUTINY_BUFFER_SIZE+8] = {1,2, static_cast<uint8_t>((datalen >> 8) & 0xFF) , static_cast<uint8_t>(datalen & 0xFF)};
  add_crc(data, SCRUTINY_BUFFER_SIZE+4);

  comm.process_data(data, sizeof(data));

  ASSERT_FALSE(comm.request_received());
  EXPECT_EQ(comm.get_rx_error(), scrutiny::Protocol::eRxErrorOverflow);
}

//=============================================================================
TEST_F(TestRxParsing, TestRx_Timeout)
{
  uint8_t data[11] = {1,2,0,3, 0x11, 0x22, 0x33};
  add_crc(data, 7);

  for (uint8_t i=1; i < sizeof(data)-1; i++)
  {
    comm.process_data(&data[0], i );
    ASSERT_FALSE(comm.request_received());
    tb.step(SCRUTINY_COMM_TIMEOUT_US);
    comm.process_data(&data[i], sizeof(data)-1 );
    ASSERT_FALSE(comm.request_received());
    comm.reset();
  }
}

//=============================================================================
TEST_F(TestRxParsing, TestRx_BadCRC)
{
  uint8_t data[11] = {1,2,0,3, 0x11, 0x22, 0x33};
  add_crc(data, 7);
  data[10] = ~data[10]; // Force bad CRC
  comm.process_data(data, sizeof(data));

  ASSERT_FALSE(comm.request_received());
}
