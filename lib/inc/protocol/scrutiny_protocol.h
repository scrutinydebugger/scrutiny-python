//    scrutiny_protocol.h
//        Main include file for the scrutiny protocol
//
//   - License : MIT - See LICENSE file.
//   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
//
//   Copyright (c) 2021-2022 scrutinydebugger

#ifndef ___SCRUTINY_PROTOCOL_H___
#define ___SCRUTINY_PROTOCOL_H___

#include "scrutiny_setup.h"

#include "protocol/scrutiny_comm_handler.h"
#include "protocol/scrutiny_protocol_definitions.h"
#if SCRUTINY_ACTUAL_PROTOCOL_VERSION == SCRUTINY_PROTOCOL_VERSION(1,0)
#include "protocol/scrutiny_codec_v1_0.h"
#endif

#endif  //___SCRUTINY_PROTOCOL_H___