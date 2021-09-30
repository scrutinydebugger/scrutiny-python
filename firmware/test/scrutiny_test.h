#include "scrutiny_crc.h"

namespace scrutiny_test
{
   void add_crc(uint8_t* data, uint16_t data_len);
   void add_crc(scrutiny::Protocol::Response* response);
}