#ifndef ___SCRUTINY_CRC_H___
#define ___SCRUTINY_CRC_H___

namespace scrutiny
{
    uint32_t crc32(const uint8_t *data, const uint32_t size, const uint32_t start_value=0);
}

#endif