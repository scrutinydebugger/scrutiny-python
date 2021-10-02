#include "scrutiny_codec_v1_0.h"
#include "scrutiny_software_id.h"

#include <cstring>

namespace scrutiny
{
namespace Protocol
{

    void CodecV1_0::encode_response_protocol_version(const ResponseData* response_data, Response* response)
    {
        response->data_length = 2;
        response->data[0] = response_data->get_info.get_protocol_version.major;
        response->data[1] = response_data->get_info.get_protocol_version.minor;
    }

    void CodecV1_0::encode_response_software_id(Response* response)
    {
        response->data_length = sizeof(scrutiny::software_id);
        std::memcpy(response->data, scrutiny::software_id, sizeof(scrutiny::software_id));
    }

}
}