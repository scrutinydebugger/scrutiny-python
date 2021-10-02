#ifndef ___SCRUTINY_PROTOCOL_H___
#define ___SCRUTINY_PROTOCOL_H___

#include "scrutiny_setup.h"
#include "scrutiny_comm_handler.h"
#include "scrutiny_protocol_definitions.h"


#define PROTOCOL_VERSION(MAJOR, MINOR) ((((MAJOR) << 8) & 0xFF) | ((MINOR) & 0xFF))
#define ACTUAL_PROTOCOL_VERSION PROTOCOL_VERSION(PROTOCOL_MAJOR, PROTOCOL_MINOR)


#if ACTUAL_PROTOCOL_VERSION == PROTOCOL_VERSION(1,0)
#include "scrutiny_codec_v1_0.h"
#endif

#endif  //___SCRUTINY_PROTOCOL_H___