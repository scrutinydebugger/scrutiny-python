#ifndef ___SCRUTINY_PROTOCOL_H___
#define ___SCRUTINY_PROTOCOL_H___

#include <cstdint>

#include "scrutiny_setup.h"
#include "scrutiny_timebase.h"

namespace scrutiny
{
    class Protocol
    {
    public:
        struct Request
        {
            void reset()
            {
                command_id = 0;
                subfunction_id = 0;
                data_length = 0;
                data = NULL;
                valid = false;
            }

            uint8_t command_id;
            uint8_t subfunction_id;
            uint16_t data_length;
            uint8_t* data;
            uint32_t crc;
            bool valid;
        };

        struct Response
        {
            void reset()
            {
                command_id = 0;
                subfunction_id = 0;
                response_code = 0;
                data_length = 0;
                data = NULL;
                valid = false;
            }

            uint8_t command_id;
            uint8_t subfunction_id;
            uint8_t response_code;
            uint16_t data_length;
            uint8_t* data;
            uint32_t crc;
            bool valid;
        };

        struct Version
        {
            uint8_t major;
            uint8_t minor;
        };

        enum RxFSMState
        {
            eRxStateWaitForCommand,
            eRxStateWaitForSubfunction,
            eRxStateWaitForLength,
            eRxStateWaitForData,
            eRxStateWaitForCRC,
            eRxStateWaitForProcess,
            eRxStateError
        };

        enum RxError
        {
            eRxErrorNone,
            eRxErrorOverflow
        };

        Protocol(uint8_t major, uint8_t minor, Timebase* timebase);
        uint8_t process_data(uint8_t* data, uint32_t len);
        void reset();
        void reset_rx();
        bool check_crc(Request* req);
        
        inline bool request_received() {return m_request_received;}
        inline Request* get_request() {return &m_active_request;}
        inline RxError get_rx_error() {return m_rx_error;}


    protected:
        Version m_version;
        Timebase *m_timebase;

        // Reception
        uint8_t m_rx_buffer[SCRUTINY_RX_BUFFER_SIZE];
        Request m_active_request;
        RxFSMState m_rx_state;
        RxError m_rx_error;
        bool m_request_received;
        uint8_t m_crc_bytes_received;
        uint8_t m_length_bytes_received;
        uint16_t m_data_bytes_received;
        uint32_t m_last_rx_timestamp;


    };
};


#endif //___SCRUTINY_PROTOCOL_H___