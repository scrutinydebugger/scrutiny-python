//    scrutiny_crc.h
//        CRC calculation functions
//
//   - License : MIT - See LICENSE file.
//   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
//
//   Copyright (c) 2021-2022 scrutinydebugger

#ifndef ___SCRUTINY_CRC_H___
#define ___SCRUTINY_CRC_H___

namespace scrutiny
{
	uint32_t crc32(const uint8_t* data, const uint32_t size, const uint32_t start_value = 0);
}

#endif