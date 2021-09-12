#ifndef __SCRUTINY_HANDLER_H__
#define __SCRUTINY_HANDLER_H__

#include "scrutiny_setup.h"
#include "scrutiny_loop_handler.h"
#include "scrutiny_timebase"

namespace scrutiny
{
    class MainHandler
    {

    public:
        void init();
        loop_id_t add_loop(ScrutinyLoop* loop);
        void process(uint32_t timestep_us);
        void process_loop(loop_id_t loop);

    private:
        ScrutinyLoop* m_loops[SCRUTINY_MAX_LOOP];
        Timebase m_timebase;
        Protocol m_protocol;

    }
};

#endif