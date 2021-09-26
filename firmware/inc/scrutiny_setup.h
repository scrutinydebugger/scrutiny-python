/**
 * @author Pier-Yves Lessard
 */

#ifndef ___SCRUTINY_SETUP_H___
#define ___SCRUTINY_SETUP_H___ 


#define SCRUTINY_MAX_LOOP 16
#define SCRUTINY_COMM_BUFFER_SIZE 256
#define SCRUTINY_COMM_TIMEOUT_US 250000 // Reset protocol state machine when no data is received for that amount of time.

namespace scrutiny
{
    typedef unsigned int loop_id_t;

 /*   struct AtomicContext{};

    inline void make_atomic(AtomicContext *previous)
    {
        // Depends on implementation. Default nothing
    }

    inline void undo_atomic(AtomicContext *previous)
    {
        // Depends on implementation. Default nothing
    }*/
};



#endif  // ___SCRUTINY_H___