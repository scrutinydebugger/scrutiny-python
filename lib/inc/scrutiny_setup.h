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

#define SCRUTINY_RX_BUFFER_SIZE 128u						// Protocol reception buffer size in bytes. Only data bytes, headers and CRC are not accounted here.
#define SCRUTINY_TX_BUFFER_SIZE 256u						// Protocol transmission buffer size in bytes. Only data bytes, headers and CRC are not accounted here.
#define SCRUTINY_COMM_RX_TIMEOUT_US 50000u					// Reset reception state machine when no data is received for that amount of time.
#define SCRUTINY_COMM_HEARTBEAT_TMEOUT_US 5000000u			// Disconnect session if no heartbeat request after this delay
#define ACTUAL_PROTOCOL_VERSION PROTOCOL_VERSION(1u, 0u)	// Protocol version to use		

#define SCRUTINY_FORBIDDEN_ADDRESS_RANGE_COUNT 4			// Number of memory range that we disallow access to Scruitny
#define SCRUTINY_READONLY_ADDRESS_RANGE_COUNT  4			// Number of memory range that we disallow write access to Scruitny

#define SCRUTINY_MAX_LOOP 16u								// Maximum number of independant time domain loops. (for datalogging)
// ================================

namespace scrutiny
{
	typedef unsigned int loop_id_t;
}


// ========================= Sanity check =====================
#if ACTUAL_PROTOCOL_VERSION != PROTOCOL_VERSION(1,0)  // Only v1.0 for now.
#error Unsupported protocol version
#endif

#if SCRUTINY_TX_BUFFER_SIZE > 0xFFFF || SCRUTINY_RX_BUFFER_SIZE > 0xFFFF
#error Scrutiny protocol is limited to 16bits data length
#endif

#if SCRUTINY_RX_BUFFER_SIZE < 32
#error Scrutiny protocol RX buffer size must be at least 32 bytes long
#endif

#if SCRUTINY_TX_BUFFER_SIZE < SOFTWARE_ID_LENGTH
#error Scrutiny protocol TX buffer must be bigger than software id
#endif

#if SCRUTINY_READONLY_ADDRESS_RANGE_COUNT < 0 || SCRUTINY_READONLY_ADDRESS_RANGE_COUNT > 0xFF
#error Invalid value for SCRUTINY_READONLY_ADDRESS_RANGE_COUNT
#endif

#if SCRUTINY_FORBIDDEN_ADDRESS_RANGE_COUNT < 0 || SCRUTINY_FORBIDDEN_ADDRESS_RANGE_COUNT > 0xFF
#error Invalid value for SCRUTINY_FORBIDDEN_ADDRESS_RANGE_COUNT
#endif

#endif  // ___SCRUTINY_H___