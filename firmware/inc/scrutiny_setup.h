/**
 * @author Pier-Yves Lessard
 */

#ifndef ___SCRUTINY_SETUP_H___
#define ___SCRUTINY_SETUP_H___ 

#include "scrutiny_software_id.h"

#define SCRUTINY_MAX_LOOP 16
#define SCRUTINY_BUFFER_SIZE 256
#define SCRUTINY_COMM_TIMEOUT_US 50000 // Reset protocol state machine when no data is received for that amount of time.


namespace scrutiny
{
    typedef unsigned int loop_id_t;
};





#if SCRUTINY_BUFFER_SIZE > 0xFFFF
   #error Scrutiny protocol is limited to 16bits data length
#endif

#if SCRUTINY_BUFFER_SIZE < SOFTWARE_ID_LENGTH
   #error Scrutiny protocol buffer must be bigger than software id
#endif

#endif  // ___SCRUTINY_H___