#include <gtest/gtest.h>

#include "scrutiny.h"

void add_crc(uint8_t* data, uint16_t data_len)
{
  uint32_t crc = scrutiny::crc32(data, data_len);
  data[data_len] = (crc >> 24) & 0xFF;
  data[data_len+1] = (crc >> 16) & 0xFF;
  data[data_len+2] = (crc >> 8) & 0xFF;
  data[data_len+3] = (crc >> 0) & 0xFF;
}


//=============================================================================
TEST(TestProtocol_V1_0, TestRx_ZeroLen_AllInOne)
{
  scrutiny::Timebase tb;
  scrutiny::Protocol::CommHandler proto;
  proto.init(1,0, &tb);

  uint8_t data[8] = {1,2,0,0};
  add_crc(data, 4);
  proto.process_data(data, sizeof(data));

  ASSERT_TRUE(proto.request_received());
  scrutiny::Protocol::Request* req = proto.get_request();
  EXPECT_EQ(req->command_id, 1);
  EXPECT_EQ(req->subfunction_id, 2);
  EXPECT_EQ(req->data_length, 0);
  
  EXPECT_EQ(proto.get_rx_error(), scrutiny::Protocol::CommHandler::eRxErrorNone);
}

//=============================================================================
TEST(TestProtocol_V1_0, TestRx_ZeroLen_BytePerByte)
{
  scrutiny::Timebase tb;
  scrutiny::Protocol::CommHandler proto;
  proto.init(1,0, &tb);

  uint8_t data[8] = {1,2,0,0};
  add_crc(data, 4);

  for (unsigned int i=0; i<sizeof(data); i++)
  {
    proto.process_data(&data[i], 1);
  }

  ASSERT_TRUE(proto.request_received());
  scrutiny::Protocol::Request* req = proto.get_request();
  EXPECT_EQ(req->command_id, 1);
  EXPECT_EQ(req->subfunction_id, 2);
  EXPECT_EQ(req->data_length, 0);

  EXPECT_EQ(proto.get_rx_error(), scrutiny::Protocol::CommHandler::eRxErrorNone);
}

//=============================================================================
TEST(TestProtocol_V1_0, TestRx_NonZeroLen_AllInOne)
{
  scrutiny::Timebase tb;
  scrutiny::Protocol::CommHandler proto;
  proto.init(1,0, &tb);

  uint8_t data[11] = {1,2,0,3, 0x11, 0x22, 0x33};
  add_crc(data, 7);
  proto.process_data(data, sizeof(data));

  ASSERT_TRUE(proto.request_received());
  scrutiny::Protocol::Request* req = proto.get_request();
  EXPECT_EQ(req->command_id, 1);
  EXPECT_EQ(req->subfunction_id, 2);
  EXPECT_EQ(req->data_length, 3);
  EXPECT_EQ(req->data[0], 0x11);
  EXPECT_EQ(req->data[1], 0x22);
  EXPECT_EQ(req->data[2], 0x33);
  
  EXPECT_EQ(proto.get_rx_error(), scrutiny::Protocol::CommHandler::eRxErrorNone);
}

//=============================================================================
TEST(TestProtocol_V1_0, TestRx_NonZeroLen_BytePerByte)
{
  scrutiny::Timebase tb;
  scrutiny::Protocol::CommHandler proto;
  proto.init(1,0, &tb);

  uint8_t data[11] = {1,2,0,3, 0x11, 0x22, 0x33};
  add_crc(data, 7);

  for (unsigned int i=0; i<sizeof(data); i++)
  {
    proto.process_data(&data[i], 1);
  }

  ASSERT_TRUE(proto.request_received());
  scrutiny::Protocol::Request* req = proto.get_request();
  EXPECT_EQ(req->command_id, 1);
  EXPECT_EQ(req->subfunction_id, 2);
  EXPECT_EQ(req->data_length, 3);
  EXPECT_EQ(req->data[0], 0x11);
  EXPECT_EQ(req->data[1], 0x22);
  EXPECT_EQ(req->data[2], 0x33);
  
  EXPECT_EQ(proto.get_rx_error(), scrutiny::Protocol::CommHandler::eRxErrorNone);
}

//=============================================================================
TEST(TestProtocol_V1_0, TestRx_Overflow)
{
  ASSERT_LT(SCRUTINY_BUFFER_SIZE, 0xFFFF-1);  // Lengths are 16bits maximum by protocol definition

  scrutiny::Timebase tb;
  scrutiny::Protocol::CommHandler proto;
  proto.init(1,0, &tb);
  uint16_t datalen = SCRUTINY_BUFFER_SIZE + 1;

  uint8_t data[SCRUTINY_BUFFER_SIZE+8] = {1,2, static_cast<uint8_t>((datalen >> 8) & 0xFF) , static_cast<uint8_t>(datalen & 0xFF)};
  add_crc(data, SCRUTINY_BUFFER_SIZE+4);

  proto.process_data(data, sizeof(data));

  ASSERT_FALSE(proto.request_received());
  EXPECT_EQ(proto.get_rx_error(), scrutiny::Protocol::CommHandler::eRxErrorOverflow);
}

//=============================================================================
TEST(TestProtocol_V1_0, TestRx_Timeout)
{
  scrutiny::Timebase tb;
  scrutiny::Protocol::CommHandler proto;
  proto.init(1,0, &tb);

  uint8_t data[11] = {1,2,0,3, 0x11, 0x22, 0x33};
  add_crc(data, 7);

  for (uint8_t i=1; i < sizeof(data)-1; i++)
  {
    proto.process_data(&data[0], i );
    ASSERT_FALSE(proto.request_received());
    tb.step(SCRUTINY_COMM_TIMEOUT_US);
    proto.process_data(&data[i], sizeof(data)-1 );
    ASSERT_FALSE(proto.request_received());
    proto.reset();
  }
}

//=============================================================================
TEST(TestProtocol_V1_0, TestRx_BadCRC)
{
  scrutiny::Timebase tb;
  scrutiny::Protocol::CommHandler proto;
  proto.init(1,0, &tb);

  uint8_t data[11] = {1,2,0,3, 0x11, 0x22, 0x33};
  add_crc(data, 7);
  data[10] = ~data[10]; // Force bad CRC
  proto.process_data(data, sizeof(data));

  ASSERT_FALSE(proto.request_received());
}
