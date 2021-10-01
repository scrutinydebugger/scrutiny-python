#ifndef ___SCRUTINY_SOFTWARE_ID_H___
#define ___SCRUTINY_SOFTWARE_ID_H___

#include <cstdint>

#define SOFTWARE_ID_LENGTH 16u
#define SOFTWARE_ID_PLACEHOLDER {0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15}

#ifndef SCRUTINY_SOFTARE_ID_CPP  // Avoid redeclaration for cpp file
namespace scrutiny
{
    extern const uint8_t software_id[SOFTWARE_ID_LENGTH];
}
#endif   // SCRUTINY_SOFTARE_ID_CPP
#endif   // ___SCRUTINY_SOFTWARE_ID_H___