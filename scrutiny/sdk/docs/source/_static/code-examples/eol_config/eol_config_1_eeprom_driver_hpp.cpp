// EEPROMDriver.hpp
#include <cstdint>

// Fictive driver, no need to know how it works.
class EEPROMDriver{
public:
    int read(uint8_t * const buf, uint32_t const addr, uint32_t const size) const;
    int write(uint8_t const * const buf, uint32_t const addr, uint32_t const size) const;
    int erase();
};
