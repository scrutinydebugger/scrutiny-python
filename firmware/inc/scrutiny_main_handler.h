#ifndef __SCRUTINY_HANDLER_H__
#define __SCRUTINY_HANDLER_H__

#include "scrutiny_setup.h"
#include "scrutiny_loop_handler.h"
#include "scrutiny_timebase.h"
#include <cstdint>

namespace scrutiny
{
    class MainHandler
    {

    public:
        void init();
        loop_id_t add_loop(LoopHandler* loop);
        void process(uint32_t timestep_us);
        void process_loop(loop_id_t loop);

    private:
        LoopHandler* m_loop_handlers[SCRUTINY_MAX_LOOP];
        Timebase m_timebase;
        //Protocol m_protocol;

    };
}

#endif