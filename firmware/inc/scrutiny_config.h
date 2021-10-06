#ifndef ___SCRUTINY_CONFIG_H___
#define ___SCRUTINY_CONFIG_H___

#include "scrutiny_setup.h"

namespace scrutiny
{
	struct AddressRange
	{
		uint64_t start;
		uint64_t end;
		bool set;
	};

	class Config
	{
	public:

		Config();
		bool add_forbidden_address_range(const uint64_t start, const uint64_t end);
		bool add_readonly_address_range(const uint64_t start, const uint64_t end);
		void copy_from(const Config* src);
		void clear();

		uint32_t get_max_bitrate() const { return m_max_bitrate; }
		void set_max_bitrate(const uint32_t val) { m_max_bitrate = val; }

	private:
		uint32_t m_max_bitrate;
		AddressRange m_forbidden_address_ranges[SCRUTINY_FORBIDDEN_ADDRESS_RANGE_COUNT];
		AddressRange m_readonly_address_ranges[SCRUTINY_READONLY_ADDRESS_RANGE_COUNT];
		uint32_t m_forbidden_range_count;
		uint32_t m_readonly_range_count;

	};
}

#endif // ___SCRUTINY_CONFIG_H___