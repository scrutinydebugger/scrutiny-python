#ifndef __SCRUTINY_HANDLER_H__
#define __SCRUTINY_HANDLER_H__

#include <cstdint>

#include "scrutiny_setup.h"
#include "scrutiny_loop_handler.h"
#include "scrutiny_timebase.h"
#include "protocol/scrutiny_protocol.h"
#include "scrutiny_config.h"


namespace scrutiny
{
    class MainHandler
    {

    public:
        void init(Config* config);
        //void process_loop(loop_id_t loop);
        //loop_id_t add_loop(LoopHandler* loop);
        
        void process(uint32_t timestep_us);
        void send_response(Protocol::Response* response);

        void process_request(Protocol::Request *request, Protocol::Response *response);
        void process_get_info(Protocol::Request *request, Protocol::Response *response);

        inline void receive_data(uint8_t* data, uint32_t len) 
        {
            m_comm_handler.process_data(data, len);
        }

    private:
        //LoopHandler* m_loop_handlers[SCRUTINY_MAX_LOOP];
        Timebase m_timebase;
        Protocol::CommHandler m_comm_handler;
        bool m_processing_request;
    };
}

#endif