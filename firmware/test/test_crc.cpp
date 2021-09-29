#include <gtest/gtest.h>
#include <cstdint>

#include "scrutiny_crc.h"

TEST(TestCRC, TestCRC32) 
{
   uint8_t data[10] = {1,2,3,4,5,6,7,8,9,10};
   uint32_t crc = crc32(data, 10);
   EXPECT_EQ(crc, 622876539);
}

