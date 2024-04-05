// EEPROmConfigurator.cpp
#include <cstring>

void EEPROMConfigurator::process()
{
    // In this function, we do some action on the EEPROM based on m_cmd, a variable that will be controlled by Scrutiny
    if (m_cmd == Command::None){
        return;
    }
    m_last_return_code = 1;
    if (m_cmd == Command::WriteAssemblyHeader)
    {
        m_last_return_code = m_driver->write(reinterpret_cast<uint8_t*>(&m_assembly_header), m_addr, sizeof(m_assembly_header));
    } 
    else if (m_cmd == Command::Write)
    {
        if (m_size < BUFFER_SIZE)
        {
            m_last_return_code = m_driver->write(m_buffer, m_addr, m_size);
        }
    }
    else if (m_cmd == Command::Read)
    {
        if (m_size < BUFFER_SIZE)
        {
            m_last_return_code = m_driver->read(m_buffer, m_addr, m_size);
        }
    }
    else if (m_cmd == Command::Erase)
    {
        m_last_return_code = m_driver->erase();
    }
    m_cmd = Command::None;
}
