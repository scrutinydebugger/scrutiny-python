#ifndef ___SCRUTINY_PROTOCOL_DEFINITION_H___
#define ___SCRUTINY_PROTOCOL_DEFINITION_H___

#include "scrutiny_software_id.h"

namespace scrutiny
{
    namespace Protocol
    {
        struct Request
        {
            void reset()
            {
                command_id = 0;
                subfunction_id = 0;
                data_length = 0;
                valid = false;
            }

            uint8_t command_id;
            uint8_t subfunction_id;
            uint16_t data_length;
            uint8_t* data;
            uint32_t crc;
            bool valid;
        };

        struct Response
        {
            void reset()
            {
                command_id = 0;
                subfunction_id = 0;
                response_code = 0;
                data_length = 0;
                valid = false;
            }

            uint8_t command_id;
            uint8_t subfunction_id;
            uint8_t response_code;
            uint16_t data_length;
            uint8_t* data;
            uint32_t crc;
            bool valid;
        };

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
                    uint8_t major;
                    uint8_t minor;
                } get_supported_features;
            } get_info;
        };

        enum CommandId
        {
            eCmdGetInfo         = 0x01,
            eCmdCommControl     = 0x02,
            eCmdMemoryControl   = 0x03,
            eCmdDataLogControl  = 0x04,
            eCmdUserCommand     = 0x05
        };


        enum ResponseCode
        {
            eResponseCode_OK = 0,
            eResponseCode_InvalidRequest = 1,
            eResponseCode_UnsupportedFeature = 2,
            eResponseCode_Overflow = 3,
            eResponseCode_Busy = 4,
            eResponseCode_FailureToProceed = 5
        };


        namespace GetInfo
        {
            enum Subfunction
            {
                eSubfnGetProtocolVersion    = 1,
                eSubfnGetSoftwareId         = 2,
                eSubfnGetSupportedFeatures  = 3
            };
        };

    }
}


#endif  // ___SCRUTINY_PROTOCOL_DEFINITION_H___