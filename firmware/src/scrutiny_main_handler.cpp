#include "scrutiny_main_handler.h"
#include "scrutiny_software_id.h"

namespace scrutiny
{


void MainHandler::init()
{
    m_processing_request = false;
    m_comm_handler.init(&m_timebase);
}

void MainHandler::process(uint32_t timestep_us)
{
    m_timebase.step(timestep_us);

    if (m_comm_handler.request_received() && !m_processing_request)
    {   
        m_processing_request = true;
        Protocol::Response *response = m_comm_handler.prepare_response();
        process_request(m_comm_handler.get_request(), response);
        if (response->valid)
        {
            m_comm_handler.send_response(response);
        }
    }

    if (m_processing_request)
    {
        if (!m_comm_handler.transmitting())  
        {
            m_comm_handler.request_processed(); // Allow reception of next request
            m_processing_request = false;
        }
    }
}


void MainHandler::process_request(Protocol::Request *request, Protocol::Response *response)
{
    response->reset();

    if (!request->valid)
        return;

    response->command_id = request->command_id;
    response->subfunction_id = request->subfunction_id;
    response->response_code = Protocol::eResponseCode_OK;
    response->valid = true;

    switch (request->command_id)
    {
        case Protocol::eCmdGetInfo:
            process_get_info(request, response);
            break;

        case Protocol::eCmdCommControl:
            break;

        case Protocol::eCmdMemoryControl:
            break;

        case Protocol::eCmdDataLogControl:
            break;

        case Protocol::eCmdUserCommand:
            break;

        default:
            response->response_code = Protocol::eResponseCode_UnsupportedFeature;
            break;
    }
}

void MainHandler::process_get_info(Protocol::Request *request, Protocol::Response *response)
{
    Protocol::ResponseData response_data;

    switch (request->subfunction_id)
    {
        case Protocol::GetInfo::eSubfnGetProtocolVersion:
            response_data.get_info.get_protocol_version.major = PROTOCOL_MAJOR;
            response_data.get_info.get_protocol_version.minor = PROTOCOL_MINOR;
            m_codec.encode_response_protocol_version(&response_data, response);
            break;

        case Protocol::GetInfo::eSubfnGetSoftwareId:
            m_codec.encode_response_software_id(response);
            break;

        case Protocol::GetInfo::eSubfnGetSupportedFeatures:
            break;

        default:
            response->response_code = Protocol::eResponseCode_UnsupportedFeature;
            break;
    }
}


/*
loop_id_t MainHandler::add_loop(LoopHandler* loop)
{
    return 0;
}

void MainHandler::process_loop(loop_id_t loop)
{
    
}
*/
}