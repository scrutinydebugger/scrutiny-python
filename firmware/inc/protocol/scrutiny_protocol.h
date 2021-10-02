#ifndef ___SCRUTINY_PROTOCOL_H___
#define ___SCRUTINY_PROTOCOL_H___

#include "scrutiny_setup.h"
#include "scrutiny_comm_handler.h"
#include "scrutiny_protocol_definitions.h"

#if PROTOCOL_MAJOR == 1 && PROTOCOL_MINOR == 0
#include "scrutiny_codec_v1_0.h"
#endif

#endif  //___SCRUTINY_PROTOCOL_H___