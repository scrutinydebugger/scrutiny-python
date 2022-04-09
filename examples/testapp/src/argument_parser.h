#ifndef ___ARGUMENT_PARSER_H___
#define ___ARGUMENT_PARSER_H___

#include <cstdint>
#include <string>

enum class TestAppCommand
{
	None,
	Memdump,
	Pipe,
	UdpListen
};


struct MemoryRegion
{
	std::uintptr_t start_address;
	uint32_t length;
};

class ArgumentParser
{
public:

	enum class Error
	{
		WrongCommand,
		Depleted
	};

	ArgumentParser();
	void parse(int argc, char* argv[]);
	void next_memory_region(MemoryRegion* region);
	bool has_another_memory_region();
	inline uint16_t udp_port() { return m_udp_port;}
	inline TestAppCommand command() { return m_command; }
	inline bool is_valid() { return m_valid; }
	std::string error_message() {return m_last_error;}

protected:
	bool m_valid;
	TestAppCommand m_command;
	unsigned int m_region_index;
	unsigned int m_argc;
	char** m_argv;
	uint16_t m_udp_port;
	std::string m_last_error;

};


#endif // ___ARGUMENT_PARSER_H___