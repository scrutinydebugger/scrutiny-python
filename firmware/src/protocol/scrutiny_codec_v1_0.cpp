#include "scrutiny_setup.h"
#include "scrutiny_codec_v1_0.h"
#include "scrutiny_software_id.h"

#include <cstring>

#pragma warning(disable:4127)

namespace scrutiny
{
namespace Protocol
{
    // ===== Encoding =====
    ResponseCode CodecV1_0::encode_response_protocol_version(const ResponseData* response_data, Response* response)
    {
        constexpr uint16_t datalen = 2;

        if (datalen > SCRUTINY_BUFFER_SIZE)
        {
            return eResponseCode_FailureToProceed;
        }

        response->data_length = datalen;
        response->data[0] = response_data->get_info.get_protocol_version.major;
        response->data[1] = response_data->get_info.get_protocol_version.minor;

        return eResponseCode_OK;
    }

    ResponseCode CodecV1_0::encode_response_software_id(Response* response)
    {
        constexpr uint16_t datalen = sizeof(scrutiny::software_id);

        if (datalen > SCRUTINY_BUFFER_SIZE)
        {
            return eResponseCode_FailureToProceed;
        }

        response->data_length = datalen;
        std::memcpy(response->data, scrutiny::software_id, sizeof(scrutiny::software_id));
        return eResponseCode_OK;
    }

    ResponseCode CodecV1_0::encode_response_comm_discover(const ResponseData* response_data, Response* response)
    {
        constexpr uint16_t magic_size = sizeof(CommControl::DISCOVER_MAGIC);
        constexpr uint16_t challenge_response_size = sizeof(response_data->comm_control.discover.challenge_response);
        constexpr uint16_t datalen = magic_size + challenge_response_size;

        if (sizeof(response_data->comm_control.discover.magic) != sizeof(CommControl::DISCOVER_MAGIC))
        {
            return eResponseCode_FailureToProceed;
        }

        if (datalen > SCRUTINY_BUFFER_SIZE)
        {
            return eResponseCode_FailureToProceed;
        }

        response->data_length = datalen;
        std::memcpy(&response->data[0], response_data->comm_control.discover.magic, magic_size);
        std::memcpy(&response->data[magic_size], response_data->comm_control.discover.challenge_response, challenge_response_size);

        return eResponseCode_OK;
    }

    ResponseCode CodecV1_0::encode_response_comm_heartbeat(const ResponseData* response_data, Response* response)
    {
        constexpr uint16_t rolling_counter_size = 1;
        constexpr uint16_t challenge_response_size = sizeof(response_data->comm_control.heartbeat.challenge_response);
        constexpr uint16_t datalen = rolling_counter_size + challenge_response_size;

        if (datalen > SCRUTINY_BUFFER_SIZE)
        {
            return eResponseCode_FailureToProceed;
        }

        response->data_length = datalen;
        response->data[0] = response_data->comm_control.heartbeat.rolling_counter;
        std::memcpy(&response->data[1], response_data->comm_control.heartbeat.challenge_response, challenge_response_size);

        return eResponseCode_OK;
    }



    // ===== Decoding =====
    ResponseCode CodecV1_0::decode_request_comm_discover(const Request* request, RequestData* request_data)
    {
        constexpr uint16_t magic_size = sizeof(CommControl::DISCOVER_MAGIC);
        constexpr uint16_t challenge_size = sizeof(request_data->comm_control.discover.challenge);
        constexpr uint16_t datalen = magic_size + challenge_size;

        if (request->data_length != datalen)
        {
            return eResponseCode_InvalidRequest;
        }

        std::memcpy(request_data->comm_control.discover.magic, request->data, magic_size);
        std::memcpy(request_data->comm_control.discover.challenge, &request->data[magic_size], challenge_size);

        return eResponseCode_OK;
    }

    ResponseCode CodecV1_0::decode_request_comm_heartbeat(const Request* request, RequestData* request_data)
    {
        constexpr uint16_t rolling_counter_size = 1;
        constexpr uint16_t challenge_size = sizeof(request_data->comm_control.heartbeat.challenge);
        constexpr uint16_t datalen = rolling_counter_size + challenge_size;

        if (request->data_length != datalen)
        {
            return eResponseCode_InvalidRequest;
        }

        request_data->comm_control.heartbeat.rolling_counter = request->data[0];
        std::memcpy(request_data->comm_control.heartbeat.challenge, &request->data[1], challenge_size);

        return eResponseCode_OK;
    }

}
}