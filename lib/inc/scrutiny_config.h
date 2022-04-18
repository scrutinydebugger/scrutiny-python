//    scrutiny_config.h
//        Definition of a run-time configuration of the scrutiny module.
//        To be filled in startup phase
//
//   - License : MIT - See LICENSE file.
//   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
//
//   Copyright (c) 2021-2022 scrutinydebugger

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
		void set_display_name(const char* name);
		void copy_from(const Config* src);
		void clear();

		inline AddressRange* forbidden_ranges() { return m_forbidden_address_ranges; }
		inline AddressRange* readonly_ranges() { return m_readonly_address_ranges; }
		inline uint8_t forbidden_ranges_count() { return m_forbidden_range_count ; }
		inline uint8_t readonly_ranges_count() { return m_readonly_range_count ; }
		inline uint32_t forbidden_ranges_max() { return SCRUTINY_FORBIDDEN_ADDRESS_RANGE_COUNT; }
		inline uint32_t readonly_ranges_max() { return SCRUTINY_READONLY_ADDRESS_RANGE_COUNT; }
		inline bool is_user_command_callback_set() { return user_command_callback != nullptr; }
		inline const char* display_name(){return m_display_name;}
		void set_display_name(char* name);
		uint32_t max_bitrate;
		user_command_callback_t user_command_callback;

	private:
		AddressRange m_forbidden_address_ranges[SCRUTINY_FORBIDDEN_ADDRESS_RANGE_COUNT];
		AddressRange m_readonly_address_ranges[SCRUTINY_READONLY_ADDRESS_RANGE_COUNT];
		uint8_t m_forbidden_range_count;
		uint8_t m_readonly_range_count;
		char m_display_name[DISPLAY_NAME_MAX_SIZE];

	};
}

#endif // ___SCRUTINY_CONFIG_H___