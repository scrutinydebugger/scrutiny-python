#ifndef ___SCRUTINY_PROTOCOL_TOOLS_H___
#define ___SCRUTINY_PROTOCOL_TOOLS_H___

#include <cstdint>

namespace scrutiny
{
	namespace Protocol
	{
		inline void encode_16_bits_big_endian(const uint16_t value, uint8_t* buff)
		{
			buff[0] = static_cast<uint8_t>((value >> 8) & 0xFF);
			buff[1] = static_cast<uint8_t>((value >> 0) & 0xFF);
		}

		inline void encode_32_bits_big_endian(const uint32_t value, uint8_t* buff)
		{
			buff[0] = static_cast<uint8_t>((value >> 24) & 0xFFu);
			buff[1] = static_cast<uint8_t>((value >> 16) & 0xFFu);
			buff[2] = static_cast<uint8_t>((value >> 8) & 0xFFu);
			buff[3] = static_cast<uint8_t>((value >> 0) & 0xFFu);
		}

		inline void encode_16_bits_little_endian(const uint16_t value, uint8_t* buff)
		{
			buff[1] = static_cast<uint8_t>((value >> 8) & 0xFFu);
			buff[0] = static_cast<uint8_t>((value >> 0) & 0xFFu);
		}

		inline void encode_32_bits_little_endian(const uint32_t value, uint8_t* buff)
		{
			buff[3] = static_cast<uint8_t>((value >> 24) & 0xFFu);
			buff[2] = static_cast<uint8_t>((value >> 16) & 0xFFu);
			buff[1] = static_cast<uint8_t>((value >> 8) & 0xFFu);
			buff[0] = static_cast<uint8_t>((value >> 0) & 0xFFu);
		}

		inline uint32_t decode_32_bits_big_endian(const uint8_t* buff)
		{
			uint32_t v = 0;
			v |= ((static_cast<uint32_t>(buff[0]) << 24) & 0xFF000000u);
			v |= ((static_cast<uint32_t>(buff[1]) << 16) & 0x00FF0000u);
			v |= ((static_cast<uint32_t>(buff[2]) << 8) & 0x0000FF00u);
			v |= ((static_cast<uint32_t>(buff[3]) << 0) & 0x000000FFu);
			return v;
		}

		inline uint16_t decode_16_bits_big_endian(const uint8_t* buff)
		{
			uint16_t v = 0;
			v |= ((static_cast<uint16_t>(buff[0]) << 8) & 0xFF00u);
			v |= ((static_cast<uint16_t>(buff[1]) << 0) & 0x00FFu);
			return v;
		}

		inline uint32_t decode_32_bits_little_endian(const uint8_t* buff)
		{
			uint32_t v = 0;
			v |= ((static_cast<uint32_t>(buff[3]) << 24) & 0xFF000000u);
			v |= ((static_cast<uint32_t>(buff[2]) << 16) & 0x00FF0000u);
			v |= ((static_cast<uint32_t>(buff[1]) << 8) & 0x0000FF00u);
			v |= ((static_cast<uint32_t>(buff[0]) << 0) & 0x000000FFu);
			return v;
		}

		inline uint16_t decode_16_bits_little_endian(const uint8_t* buff)
		{
			uint16_t v = 0;
			v |= ((static_cast<uint16_t>(buff[1]) << 8) & 0xFF00u);
			v |= ((static_cast<uint16_t>(buff[0]) << 0) & 0x00FFu);
			return v;
		}
	}
}

#endif //___SCRUTINY_PROTOCOL_TOOLS_H___