//    scrutiny_crc.cpp
//        CRC calculation for scrutiny protocol frames
//
//   - License : MIT - See LICENSE file.
//   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
//
//   Copyright (c) 2021-2022 scrutinydebugger

#include <cstdint>

namespace scrutiny
{
	uint32_t crc32(const uint8_t* data, const uint32_t size, const uint32_t start_value)
	{
		uint32_t crc = ~start_value;

		for (uint32_t i = 0; i < size; i++)
		{
			uint8_t byte = data[i];
			for (unsigned int j = 0; j < 8; j++)
			{
				const unsigned int lsb = (byte ^ crc) & 1;
				crc >>= 1;
				if (lsb)
				{
					crc ^= 0xEDB88320;
				}
				byte >>= 1;
			}
		}

		return ~crc;
	}
}