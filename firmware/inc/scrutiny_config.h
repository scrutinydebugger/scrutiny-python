#ifndef ___SCRUTINY_CONFIG_H___
#define ___SCRUTINY_CONFIG_H___

#include "scrutiny_setup.h"
#include "scrutiny_types.h"

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
		bool add_forbidden_address_range(void* start, void* end);
		bool add_readonly_address_range(void* start, void* end);
		void copy_from(const Config* src);
		void clear();

		inline AddressRange* forbidden_ranges() { return m_forbidden_address_ranges; }
		inline AddressRange* readonly_ranges() { return m_readonly_address_ranges; }
		inline uint32_t forbidden_ranges_max() { return SCRUTINY_FORBIDDEN_ADDRESS_RANGE_COUNT; }
		inline uint32_t readonly_ranges_max() { return SCRUTINY_READONLY_ADDRESS_RANGE_COUNT; }
		inline bool is_user_command_callback_set() { return user_command_callback != nullptr; }
		uint32_t max_bitrate;
		user_command_callback_t user_command_callback;
	private:
		AddressRange m_forbidden_address_ranges[SCRUTINY_FORBIDDEN_ADDRESS_RANGE_COUNT];
		AddressRange m_readonly_address_ranges[SCRUTINY_READONLY_ADDRESS_RANGE_COUNT];
		uint32_t m_forbidden_range_count;
		uint32_t m_readonly_range_count;

	};
}

#endif // ___SCRUTINY_CONFIG_H___