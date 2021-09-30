#include <cstdint>
#include "scrutiny.h"

namespace scrutiny_test
{
   void add_crc(uint8_t* data, uint16_t data_len)
   {
     uint32_t crc = scrutiny::crc32(data, data_len);
     data[data_len] = (crc >> 24) & 0xFF;
     data[data_len+1] = (crc >> 16) & 0xFF;
     data[data_len+2] = (crc >> 8) & 0xFF;
     data[data_len+3] = (crc >> 0) & 0xFF;
   }
}