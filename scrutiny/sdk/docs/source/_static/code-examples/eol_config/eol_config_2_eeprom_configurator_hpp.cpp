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
