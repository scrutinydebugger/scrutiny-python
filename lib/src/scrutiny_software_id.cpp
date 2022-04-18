//    scrutiny_software_id.cpp
//        Instanciation of the global ID used for firmware tagging
//
//   - License : MIT - See LICENSE file.
//   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
//
//   Copyright (c) 2021-2022 scrutinydebugger

#include <cstdint>

#include "scrutiny_software_id.h"

namespace scrutiny
{
	extern const uint8_t software_id[SCRUTINY_SOFTWARE_ID_LENGTH] = SCRUTINY_SOFTWARE_ID_PLACEHOLDER;
}