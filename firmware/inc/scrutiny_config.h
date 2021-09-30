#ifndef ___SCRUTINY_CONFIG_H___
#define ___SCRUTINY_CONFIG_H___

#include <cstdint>

namespace scrutiny
{
    struct Config
    {
        uint8_t protocol_major;
        uint8_t protocol_minor;
    };
}

#endif