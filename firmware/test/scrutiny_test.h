#include <gtest/gtest.h>

#include "scrutiny_crc.h"

#define ASSERT_BUF_EQ(a,b,c) ASSERT_TRUE(COMPARE_BUF(a, b, c))
#define EXPECT_BUF_EQ(a,b,c) EXPECT_TRUE(COMPARE_BUF(a, b, c))

class ScrutinyTest : public ::testing::Test 
{
protected:

   void add_crc(uint8_t* data, uint16_t data_len);
   void add_crc(scrutiny::Protocol::Response* response);

   ::testing::AssertionResult COMPARE_BUF( const uint8_t* candidate, const uint8_t* expected, const uint32_t size);

};