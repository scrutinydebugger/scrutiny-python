#include "scrutiny_config.h"

namespace scrutiny
{
    Config::Config()
    {
        clear();  
    }


    void Config::copy_from(const Config* src)
    {
        clear();
        m_max_bitrate = src->m_max_bitrate;

        for (uint32_t i=0; i<SCRUTINY_FORBIDDEN_ADDRESS_RANGE_COUNT; i++)
        {
            if (src->m_forbidden_address_ranges[i].set)
            {
                add_forbidden_address_range(src->m_forbidden_address_ranges[i].start, src->m_forbidden_address_ranges[i].end);
            }
        }

        for (uint32_t i=0; i<SCRUTINY_READONLY_ADDRESS_RANGE_COUNT; i++)
        {
            if (src->m_readonly_address_ranges[i].set)
            {
                add_readonly_address_range(src->m_readonly_address_ranges[i].start, src->m_readonly_address_ranges[i].end);
            }
        }
    }

    void Config::clear()
    {
        m_max_bitrate = 0;
        for (uint32_t i=0; i<SCRUTINY_FORBIDDEN_ADDRESS_RANGE_COUNT; i++)
        {
            m_forbidden_address_ranges[i].set = false;
        }

        for (uint32_t i=0; i<SCRUTINY_READONLY_ADDRESS_RANGE_COUNT; i++)
        {
            m_readonly_address_ranges[i].set = false;
        } 

        m_forbidden_range_count = 0;
        m_readonly_range_count = 0;
    }

    bool Config::add_forbidden_address_range(const uint64_t start, const uint64_t end)
    {
        if (m_forbidden_range_count == SCRUTINY_FORBIDDEN_ADDRESS_RANGE_COUNT)
        {
            return false;
        }

        m_forbidden_address_ranges[m_forbidden_range_count].start = start;
        m_forbidden_address_ranges[m_forbidden_range_count].end = end;
        m_forbidden_address_ranges[m_forbidden_range_count].set = true;
        m_forbidden_range_count++;
        return true;
    }

    bool Config::add_readonly_address_range(const uint64_t start, const uint64_t end)
    {
        if (m_readonly_range_count == SCRUTINY_READONLY_ADDRESS_RANGE_COUNT)
        {
            return false;
        }   

        m_readonly_address_ranges[m_readonly_range_count].start = start;
        m_readonly_address_ranges[m_readonly_range_count].end = end;
        m_readonly_address_ranges[m_readonly_range_count].set = true;
        m_readonly_range_count++;
        return true;
    }

}