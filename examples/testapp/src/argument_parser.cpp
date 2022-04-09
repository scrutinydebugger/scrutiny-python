#include <cstdlib>
#include <string>
#include <algorithm>

#include "argument_parser.h"


ArgumentParser::ArgumentParser() :
	m_valid(false),
	m_command(TestAppCommand::None),
	m_region_index(0),
	m_argc(0),
	m_argv(nullptr),
	m_last_error()
{

}

void ArgumentParser::parse(int argc, char* argv[])
{
	m_argc = argc;
	m_argv = argv;
	if (argc < 2)
	{
		m_valid = false;
		m_last_error = "Missing command";
		return;
	}

	std::string cmd(argv[1]);
	std::transform(cmd.begin(), cmd.end(), cmd.begin(), [](unsigned char c) { return static_cast<unsigned char>(std::tolower(c)); });

	if (cmd == "memdump")
	{
		m_command = TestAppCommand::Memdump;

		if (argc >= 4 && argc % 2 == 0)
		{
			m_valid = true;
		}
		else
		{
			m_last_error = "Bad number of arguments";
		}
	}
	else if (cmd == "pipe")
	{
		m_command = TestAppCommand::Pipe;
		m_valid = true;
	}
	else if (cmd == "udp-listen")
	{
		m_command = TestAppCommand::UdpListen;
		if (argc >= 3)
		{
			int32_t port = atoi(m_argv[2]);
			if (port > 0 && port <0x10000)
			{
				m_udp_port = static_cast<uint16_t>(port);
				m_valid = true;
			}
			else
			{
				m_last_error = "Port not in range 0-65535";
			}
		}
		else
		{
			m_last_error = "Missing port";
		}
	}
	else
	{
		m_last_error = std::string("Unknown command ") + cmd;
	}
}

bool ArgumentParser::has_another_memory_region()
{
	if (m_argc < 2)
	{
		return false;
	}

	if (m_argc - 2 < m_region_index + 1)
	{
		return false;
	}

	return true;
}

void ArgumentParser::next_memory_region(MemoryRegion* region)
{
	constexpr uint32_t region_offset = 2;
	if (m_command != TestAppCommand::Memdump || !m_valid)
	{
		throw Error::WrongCommand;
	}

	if (!has_another_memory_region())
	{
		throw Error::Depleted;
	}

	int base1 = 10;
	int base2 = 10;
	std::string start_address(m_argv[m_region_index + region_offset]);
	if (start_address.length() > 2 && start_address.find("0x") == 0)
	{
		start_address = start_address.substr(2);
		base1 = 16;
	}

	std::string length(m_argv[m_region_index + region_offset + 1]);
	if (length.length() > 2 && length.find("0x") == 0)
	{
		length = length.substr(2);
		base2 = 16;
	}

	region->start_address = static_cast<std::uintptr_t>(strtoll(start_address.c_str(), NULL, base1));
	region->length = static_cast<uint32_t>(strtol(length.c_str(), NULL, base2));

	m_region_index += 2;

}