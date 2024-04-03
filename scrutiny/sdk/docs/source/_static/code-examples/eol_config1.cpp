// ----------------
// EEPROMDriver.hpp
#include <cstdint>

// Fictive driver, no need to know how it works.
class EEPROMDriver{
public:
    int read(uint8_t * const buf, uint32_t const addr, uint32_t const size) const;
    int write(uint8_t const * const buf, uint32_t const addr, uint32_t const size) const;
    int erase();
};

// ----------------
// EEPROmConfigurator.hpp

class EEPROMConfigurator{
public:
    static constexpr uint32_t BUFFER_SIZE=1024;
    enum class Command{
        None,
        Read,
        Write,
        WriteAssemblyHeader,
        Erase
    };

    struct AssemblyHeader {
        uint8_t model;
        uint8_t version;
        uint8_t revision;
        uint32_t serial;
    };

    EEPROMConfigurator(EEPROMDriver* const driver) : 
        m_buffer{},
        m_size{0},
        m_addr{0},
        m_buffer_size{BUFFER_SIZE},
        m_driver{driver},
        m_cmd{Command::None},
        m_assembly_header{},
        m_last_return_code{0}
        {}
    void process();
private:
    uint8_t m_buffer[BUFFER_SIZE];
    uint32_t m_size;
    uint32_t m_addr;
    uint32_t m_buffer_size;
    EEPROMDriver* const m_driver;
    Command m_cmd;
    AssemblyHeader m_assembly_header;
    int m_last_return_code;
};


// ----------------
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


//-----------------
// main.cpp

void init();
void run_application();
void update_scrutiny();

EEPROMDriver eeprom_driver;
#ifdef ENABLE_EOL_CONFIGURATOR
EEPROMConfigurator eeprom_configurator(&eeprom_driver);
#endif

int main()
{
    init();
    while(true)
    {
#ifdef ENABLE_EOL_CONFIGURATOR
        eeprom_configurator.process();
#endif
        run_application();
        update_scrutiny();
    }
}
