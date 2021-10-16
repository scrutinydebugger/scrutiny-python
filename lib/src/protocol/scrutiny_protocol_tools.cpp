#include "protocol/scrutiny_protocol_tools.h"

#include <cstdint>

namespace scrutiny
{
	namespace protocol
	{

		uint8_t decode_address_big_endian(uint8_t* buf, uint64_t* addr)
		{
			uint64_t computed_addr = 0;

			unsigned int i = 0;
			switch (sizeof(void*))
			{
			case 8:
				computed_addr |= ((static_cast<uint64_t>(buf[i++]) << 56));
				computed_addr |= ((static_cast<uint64_t>(buf[i++]) << 48));
				computed_addr |= ((static_cast<uint64_t>(buf[i++]) << 40));
				computed_addr |= ((static_cast<uint64_t>(buf[i++]) << 32));
			case 4:
				computed_addr |= ((static_cast<uint64_t>(buf[i++]) << 24));
				computed_addr |= ((static_cast<uint64_t>(buf[i++]) << 16));
			case 2:
				computed_addr |= ((static_cast<uint64_t>(buf[i++]) << 8));
			case 1:
				computed_addr |= ((static_cast<uint64_t>(buf[i++]) << 0));
			default:
				break;
			}

			*addr = computed_addr;

			return static_cast<uint8_t>(i);
		}

		uint8_t encode_address_big_endian(uint8_t* buf, void* ptr)
		{
			return encode_address_big_endian(buf, reinterpret_cast<uint64_t>(ptr));
		}

		uint8_t encode_address_big_endian(uint8_t* buf, uint64_t addr)
		{
			unsigned int i = 0;
			switch (sizeof(void*))
			{
			case 8:
				buf[i++] = static_cast<uint8_t>((addr >> 56) & 0xFF);
				buf[i++] = static_cast<uint8_t>((addr >> 48) & 0xFF);
				buf[i++] = static_cast<uint8_t>((addr >> 40) & 0xFF);
				buf[i++] = static_cast<uint8_t>((addr >> 32) & 0xFF);
			case 4:
				buf[i++] = static_cast<uint8_t>((addr >> 24) & 0xFF);
				buf[i++] = static_cast<uint8_t>((addr >> 16) & 0xFF);
			case 2:
				buf[i++] = static_cast<uint8_t>((addr >> 8) & 0xFF);
			case 1:
				buf[i++] = static_cast<uint8_t>((addr >> 0) & 0xFF);
			default:
				break;
			}

			return static_cast<uint8_t>(i);
		}

	}
}
