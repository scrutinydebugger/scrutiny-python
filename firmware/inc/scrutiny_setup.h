/**
 * @author Pier-Yves Lessard
 */

#ifndef ___SCRUTINY_SETUP_H___
#define ___SCRUTINY_SETUP_H___ 

#ifdef __GNUC__
    #ifdef ALIGNMENT
    #define __ALIGNED__ __attribute__((aligned(ALIGNMENT)))
    #else
    #define __ALIGNED__ __attribute__((aligned(4))) // default align 4 for maximum compatibility
    #endif
#else
#error "Alignment not handled for this compiler"
#endif

#define SCRUTINY_MAX_LOOP 16
#define SCRUTINY_COMM_BUFFER_SIZE 256
#define SCRUTINY_COMM_TIMEOUT_US 250000 // Reset protocol state machine when no data is received for that amount of time.

namespace Scrutiny
{
    typedef loop_id_t unsigned int;
};



#endif  // ___SCRUTINY_H___