//    scrutiny_protocol_tools.cpp
//        Some helpers for encoding data in a standardised way.
//        similar to hton() and ntoh()
//
//   - License : MIT - See LICENSE file.
//   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
//
//   Copyright (c) 2021-2022 scrutinydebugger

#include "protocol/scrutiny_protocol_tools.h"

#include <cstdint>

namespace scrutiny
{
	namespace protocol
	{
#if defined(_MSC_VER)
#pragma warning(push)
#pragma warning(disable:4127)   // Get rid of constexpr always true condition warning.
#endif 
		uint8_t decode_address_big_endian(uint8_t* buf, uint64_t* addr)
		{
			constexpr unsigned int addr_size = sizeof(void*);
			static_assert(addr_size == 1 || addr_size == 2 || addr_size == 4 || addr_size == 8, "Unsupported address size");

			uint64_t computed_addr = 0;
			unsigned int i = 0;

			if (addr_size >= 8)
			{
				computed_addr |= ((static_cast<uint64_t>(buf[i++]) << 56));
				computed_addr |= ((static_cast<uint64_t>(buf[i++]) << 48));
				computed_addr |= ((static_cast<uint64_t>(buf[i++]) << 40));
				computed_addr |= ((static_cast<uint64_t>(buf[i++]) << 32));
			}

			if (addr_size >= 4)
			{
				computed_addr |= ((static_cast<uint64_t>(buf[i++]) << 24));
				computed_addr |= ((static_cast<uint64_t>(buf[i++]) << 16));
			}

			if (addr_size >= 2)
			{
				computed_addr |= ((static_cast<uint64_t>(buf[i++]) << 8));
			}

			if (addr_size >= 1)
			{
				computed_addr |= ((static_cast<uint64_t>(buf[i++]) << 0));
			}
			
			*addr = computed_addr;

			return static_cast<uint8_t>(addr_size);
		}
#if defined(_MSC_VER)
#pragma warning(pop)
#endif		

		uint8_t encode_address_big_endian(uint8_t* buf, void* ptr)
		{
			return encode_address_big_endian(buf, reinterpret_cast<uint64_t>(ptr));
		}


#if defined(_MSC_VER)
#pragma warning(push)
#pragma warning(disable:4127)   // Get rid of constexpr always true condition warning.
#endif 
		uint8_t encode_address_big_endian(uint8_t* buf, register uint64_t addr)
		{
			constexpr unsigned int addr_size = sizeof(void*);
			static_assert(addr_size == 1 || addr_size == 2 || addr_size == 4 || addr_size == 8, "Unsupported address size");

			unsigned int i = addr_size-1;

			if (addr_size >= 1)
			{
				buf[i--] = static_cast<uint8_t>((addr >> 0) & 0xFF);
			}

			if (addr_size >= 2)
			{
				buf[i--] = static_cast<uint8_t>((addr >> 8) & 0xFF);
			}

			if (addr_size >= 4)
			{
				buf[i--] = static_cast<uint8_t>((addr >> 16) & 0xFF);
				buf[i--] = static_cast<uint8_t>((addr >> 24) & 0xFF);
			}

			if (addr_size == 8)
			{
				buf[i--] = static_cast<uint8_t>((addr >> 32) & 0xFF);
				buf[i--] = static_cast<uint8_t>((addr >> 40) & 0xFF);
				buf[i--] = static_cast<uint8_t>((addr >> 48) & 0xFF);
				buf[i--] = static_cast<uint8_t>((addr >> 56) & 0xFF);
			}

			return static_cast<uint8_t>(addr_size);
		}
#if defined(_MSC_VER)
#pragma warning(pop)
#endif			
	}
}
