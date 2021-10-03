/**
 * @author Pier-Yves Lessard
 */

#ifndef ___SCRUTINY_SETUP_H___
#define ___SCRUTINY_SETUP_H___ 

#include "scrutiny_software_id.h"

#define PROTOCOL_VERSION(MAJOR, MINOR) ((((MAJOR) << 8) & 0xFF00) | ((MINOR) & 0xFF))
#define PROTOCOL_VERSION_MAJOR(v) ((v>>8) & 0xFF)
#define PROTOCOL_VERSION_MINOR(v) (v & 0xFF)

// ========== Parameters ==========

#define SCRUTINY_BUFFER_SIZE 256u
#define SCRUTINY_COMM_TIMEOUT_US 50000u                     // Reset reception state machine when no data is received for that amount of time.
#define SCRUTINY_COMM_HEARTBEAT_TMEOUT_US 5000000u
#define ACTUAL_PROTOCOL_VERSION PROTOCOL_VERSION(1u, 0u)

#define SCRUTINY_FORBIDDEN_ADDRESS_RANGE_COUNT 4
#define SCRUTINY_READONLY_ADDRESS_RANGE_COUNT  4

#define SCRUTINY_MAX_LOOP 16u
// ================================


namespace scrutiny
{
    typedef unsigned int loop_id_t;
};


// ========================= Sanity check =====================
#if ACTUAL_PROTOCOL_VERSION != PROTOCOL_VERSION(1,0)  // Only v1.0 for now.
#error Unsupported protocol version
#endif

#if SCRUTINY_BUFFER_SIZE > 0xFFFF
   #error Scrutiny protocol is limited to 16bits data length
#endif

#if SCRUTINY_BUFFER_SIZE < 32
   #error Scrutiny protocol buffer size must be at least 32 bytes long
#endif

#if SCRUTINY_BUFFER_SIZE < SOFTWARE_ID_LENGTH
   #error Scrutiny protocol buffer must be bigger than software id
#endif

#endif  // ___SCRUTINY_H___