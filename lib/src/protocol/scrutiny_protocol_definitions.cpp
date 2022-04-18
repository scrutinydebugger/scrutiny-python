//    scrutiny_protocol_definitions.cpp
//        Instanciation of protocol definitions such as magic payload.
//
//   - License : MIT - See LICENSE file.
//   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
//
//   Copyright (c) 2021-2022 scrutinydebugger

#include <cstdint>
#include "protocol/scrutiny_protocol_definitions.h"

//Randomly generated
extern const uint8_t scrutiny::protocol::CommControl::DISCOVER_MAGIC[4] = { 0x7E, 0x18, 0xFC, 0x68 };
extern const uint8_t scrutiny::protocol::CommControl::CONNECT_MAGIC[4] = { 0x82, 0x90, 0x22, 0x66 };
