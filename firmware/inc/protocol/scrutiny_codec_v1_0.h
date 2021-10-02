#ifndef ___SCRUTINY_CODEC_V1_0___
#define ___SCRUTINY_CODEC_V1_0___

#include <cstdint>
#include "scrutiny_protocol_definitions.h"


namespace scrutiny
{
    namespace Protocol
    {
        union ResponseData
        {
            union
            {
                struct 
                {
                    uint8_t major;
                    uint8_t minor;
                } get_protocol_version;

                struct 
                {
                    uint8_t temp;
                } get_supported_features;
            } get_info;
        };


        class CodecV1_0
        {
        public:
            void encode_response_protocol_version(const ResponseData* response_data, Response* response);
            void encode_response_software_id( Response* response);
        } ;
    }
}
#endif // ___SCRUTINY_CODEC_V1_0___