#ifndef ___SCRUTINY_TIMEBASE_H___
#define ___SCRUTINY_TIMEBASE_H___

#include <cstdint>

namespace scrutiny
{
    class Timebase
    {
    public:
        Timebase() : m_time_us(0) {}
        inline void step(uint32_t timestep_us)  
        { 
            m_time_us += timestep_us;
        }

        inline uint32_t get_timestamp() {
            return m_time_us;
        };

        bool is_elpased(uint32_t timestamp, uint32_t timeout_us)
        {
            bool elapsed = false;
            if (timestamp > m_time_us)
            {
                diff = timestamp - m_time_us;
                if (timestamp - m_time_us >= timeout_us)
                    elapsed =  true;
            }
            else
            {

            }
            
            return elapsed
        }

    protected:
        uint32_t m_time_us;
    };
}


#endif