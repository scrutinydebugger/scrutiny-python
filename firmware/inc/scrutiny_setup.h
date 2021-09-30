/**
 * @author Pier-Yves Lessard
 */

#ifndef ___SCRUTINY_SETUP_H___
#define ___SCRUTINY_SETUP_H___ 


#define SCRUTINY_MAX_LOOP 16
#define SCRUTINY_BUFFER_SIZE 256
#define SCRUTINY_COMM_TIMEOUT_US 50000 // Reset protocol state machine when no data is received for that amount of time.

#define SOFTWARE_ID_PLACEHOLDER {1,2,3,4}
#define SOFTWARE_ID_LENGTH 4


namespace scrutiny
{
    typedef unsigned int loop_id_t;
};



#endif  // ___SCRUTINY_H___