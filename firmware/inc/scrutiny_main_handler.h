#ifndef __SCRUTINY_HANDLER_H__
#define __SCRUTINY_HANDLER_H__

#include <cstdint>

#include "scrutiny_setup.h"
#include "scrutiny_loop_handler.h"
#include "scrutiny_timebase.h"
#include "scrutiny_protocol.h"

namespace scrutiny
{
    class MainHandler
    {

    public:
        void init();
        //void process_loop(loop_id_t loop);
        //loop_id_t add_loop(LoopHandler* loop);
        
        void process(uint32_t timestep_us);

        void process_request(Protocol::Request *request, Protocol::Response *response);
        void process_get_info(Protocol::Request *request, Protocol::Response *response);

        inline void receive_data(uint8_t* data, uint32_t len) 
        {
            m_comm_handler.process_data(data, len);
        }

        inline uint32_t data_to_send()
        {
            return m_comm_handler.data_to_send();
        }

        inline uint32_t pop_data(uint8_t* buffer, uint32_t len)
        {
            return m_comm_handler.pop_data(buffer, len);
        } 

    private:
        //LoopHandler* m_loop_handlers[SCRUTINY_MAX_LOOP];
        Timebase m_timebase;
        Protocol::CommHandler<PROTOCOL_MAJOR, PROTOCOL_MINOR> m_comm_handler;
        bool m_processing_request;
#if (PROTOCOL_MAJOR == 1) && (PROTOCOL_MINOR == 0)
        Protocol::CodecV1_0 m_codec;
#endif
    };
}

#endif