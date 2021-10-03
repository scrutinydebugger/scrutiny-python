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

            union 
            {
                struct
                {
                    uint8_t magic[sizeof(CommControl::DISCOVER_MAGIC)];
                    uint8_t challenge_response[4];
                } discover;
                struct
                {
                    uint8_t rolling_counter;
                    uint8_t challenge_response[2];
                } heartbeat;
            } comm_control;
        };


        union RequestData
        {
            union 
            {
                struct
                {
                    uint8_t magic[sizeof(CommControl::DISCOVER_MAGIC)];
                    uint8_t challenge[4];
                } discover;
                
                struct 
                {
                    uint8_t rolling_counter;
                    uint8_t challenge[2];
                } heartbeat;
            } comm_control;
        };


        class CodecV1_0
        {
        public:
            ResponseCode encode_response_protocol_version(const ResponseData* response_data, Response* response);
            ResponseCode encode_response_software_id( Response* response);
            ResponseCode encode_response_comm_discover(const ResponseData* response_data, Response* response);
            ResponseCode encode_response_comm_heartbeat(const ResponseData* response_data, Response* response);

            ResponseCode decode_request_comm_discover(const Request* request, RequestData* request_data);
            ResponseCode decode_request_comm_heartbeat(const Request* request, RequestData* request_data);
        } ;
    }
}
#endif // ___SCRUTINY_CODEC_V1_0___