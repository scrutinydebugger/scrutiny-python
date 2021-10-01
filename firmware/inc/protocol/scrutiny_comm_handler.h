#ifndef ___SCRUTINY_COMM_HANDLER_H___
#define ___SCRUTINY_COMM_HANDLER_H___

#include <cstdint>

#include "scrutiny_setup.h"
#include "scrutiny_timebase.h"
#include "protocol/scrutiny_protocol_definitions.h"

namespace scrutiny
{
    namespace Protocol
    {
        class CommHandler
        {
        public:
            enum RxError
            {
                eRxErrorNone,
                eRxErrorOverflow
            };

            enum TxError
            {
                eTxErrorNone,
                eTxErrorOverflow,
                eTxErrorBusy
            };

            struct Version
            {
                uint8_t major;
                uint8_t minor;
            };
            
            void init(uint8_t major, uint8_t minor, Timebase* timebase);
            void process_data(uint8_t* data, uint32_t len);
            bool send_response(Response* response);
            void reset();
            Response* prepare_response();

            uint32_t pop_data(uint8_t* buffer, uint32_t len);
            uint32_t data_to_send();

            bool check_crc(Request* req);
            void add_crc(Response* response);
            
            inline void request_processed() { reset_rx();}
            inline Version get_version() { return m_version;}
            inline bool request_received() {return m_request_received;}
            inline Request* get_request() {return &m_active_request;}
            inline RxError get_rx_error() {return m_rx_error;}
            inline bool transmitting() {return (m_state == eStateTransmitting);}
            inline bool receiving() {return (m_state == eStateReceiving);}



            void encode_response_protocol_version(const ResponseData* response_data, Response* response);
            void encode_response_software_id( Response* response);

        protected:

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

            enum State
            {
                eStateIdle,
                eStateReceiving,
                eStateTransmitting,
            };

            void reset_rx();
            void reset_tx();

            Version m_version;
            Timebase *m_timebase;
            State m_state;

            // Reception
            uint8_t m_buffer[SCRUTINY_BUFFER_SIZE];
            Request m_active_request;
            RxFSMState m_rx_state;
            RxError m_rx_error;
            bool m_request_received;
            uint8_t m_crc_bytes_received;
            uint8_t m_length_bytes_received;
            uint16_t m_data_bytes_received;
            uint32_t m_last_rx_timestamp;


            // Transmission
            Response m_active_response;
            uint32_t m_nbytes_to_send;
            uint32_t m_nbytes_sent;
            TxError m_tx_error;
        };
    };
};




#endif //___SCRUTINY_COMM_HANDLER_H___