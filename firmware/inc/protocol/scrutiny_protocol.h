#ifndef ___SCRUTINY_PROTOCOL_H___
#define ___SCRUTINY_PROTOCOL_H___

#include <cstdint>

#include "scrutiny_setup.h"
#include "scrutiny_timebase.h"

namespace scrutiny
{

    class Protocol
    {

        struct Version
        {
            uint8_t major,
            uint8_t minor
        };

    public:
        Protocol(uint8_t major, uint8_t minor, Timebase timebase);
        uint8_t process_data(uint8_t* data, uint32_t len);
        bool command_ready();


    protected:
        Version m_version;
        uint8_t _rx_buffer[SCRUTINY_COMM_BUFFER_SIZE] __ALIGNED__
        
    };
};


#endif ___SCRUTINY_PROTOCOL_H___