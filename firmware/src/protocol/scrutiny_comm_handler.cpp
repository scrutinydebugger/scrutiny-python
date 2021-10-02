#include <cstring>

#include "scrutiny_comm_handler.h"
#include "scrutiny_crc.h"

namespace scrutiny
{
namespace Protocol
{
    void CommHandler::init(Timebase* timebase)
    {
        m_timebase = timebase;

        m_active_request.data = m_buffer;   // Half duplex comm. Share buffer
        m_active_response.data = m_buffer;  // Half duplex comm. Share buffer
        m_enabled = false;

        reset();
    }

    void CommHandler::process_data(uint8_t* data, uint32_t len)
    {
        uint32_t i = 0;

        if (m_state == eStateTransmitting)
        {
            return; // Half duplex comm. Discard data;
        }
        
        // Handle rx timeouts. Start a new reception if no data for too long
        if (m_rx_state != eRxStateWaitForCommand && len !=0 )
        {
            if (m_timebase->is_elapsed(m_last_rx_timestamp, SCRUTINY_COMM_TIMEOUT_US))
            {
                reset_rx();
                m_state = eStateIdle;
            }
        }

        // Update rx timestamp
        if (len != 0)
        {
            m_last_rx_timestamp = m_timebase->get_timestamp();

            if (m_state == eStateIdle)
            {
                m_state = eStateReceiving;
            }
        }

        // Process each bytes
        while (i < len && !m_request_received && m_rx_state != eRxStateError)
        {
            switch (m_rx_state) // FSM
            {
                case eRxStateWaitForCommand:
                {
                    m_active_request.command_id = data[i] & 0x7F;
                    m_rx_state = eRxStateWaitForSubfunction;
                    i+=1;
                    break;
                }
                
                case eRxStateWaitForSubfunction:
                {
                    m_active_request.subfunction_id = data[i];
                    m_rx_state = eRxStateWaitForLength;
                    i+=1;
                    break;
                }
                
                case eRxStateWaitForLength:
                {
                    bool next_state = false;
                    if (m_length_bytes_received == 0)
                    {
                        if ( (len-i) >= 2)
                        {
                            m_active_request.data_length = ( ((uint16_t)data[i]) << 8 ) | ((uint16_t)data[i+1]);
                            m_length_bytes_received = 2;
                            i+=2;
                            next_state = true;
                        }
                        else
                        {
                            m_active_request.data_length = ( ((uint16_t)data[i]) << 8 ) ;
                            m_length_bytes_received = 1;
                            i+=1;
                        }
                    }
                    else
                    {
                        m_active_request.data_length |= ((uint16_t)data[i]);
                        m_length_bytes_received = 2;
                        i+=1;
                        next_state = true;
                    }

                    if (next_state)
                    {
                        if (m_active_request.data_length == 0)
                        {
                            m_rx_state = eRxStateWaitForCRC;
                        }
                        else
                        {
                            m_rx_state = eRxStateWaitForData;
                        }
                    }
                    break;
                }

                case eRxStateWaitForData:
                {
                    if (m_active_request.data_length > SCRUTINY_BUFFER_SIZE)
                    {
                        m_rx_error = eRxErrorOverflow;
                        m_rx_state = eRxStateError;
                        break;
                    }

                    const uint16_t available_bytes = static_cast<uint16_t>(len-i);
                    const uint16_t missing_bytes = m_active_request.data_length - m_data_bytes_received;
                    const uint16_t data_bytes_to_read = (available_bytes >= missing_bytes) ? missing_bytes : available_bytes;

                    std::memcpy(&m_buffer[m_data_bytes_received], &data[i], data_bytes_to_read);
                    m_data_bytes_received += data_bytes_to_read;
                    i += data_bytes_to_read;

                    if (m_data_bytes_received >= m_active_request.data_length)
                    {
                        m_rx_state = eRxStateWaitForCRC;
                    }

                    break;
                }

                case eRxStateWaitForCRC:
                {
                    if (m_crc_bytes_received == 0)
                    {
                        m_active_request.crc = ((uint32_t)data[i]) << 24;
                    }
                    else if (m_crc_bytes_received == 1)
                    {
                        m_active_request.crc |= ((uint32_t)data[i]) << 16;
                    }
                    else if (m_crc_bytes_received == 2)
                    {
                        m_active_request.crc |= ((uint32_t)data[i]) << 8;
                    }
                    else if (m_crc_bytes_received == 3)
                    {
                        m_active_request.crc |= ((uint32_t)data[i]) << 0;
                        m_state = eStateIdle;

                        if (check_crc(&m_active_request))
                        {
                            if (m_enabled == false)
                            {
                                if (check_must_enable())    // Check if we received a valid discover message
                                {
                                    m_enabled = true;
                                }
                            }

                            if (m_enabled)
                            {
                                m_active_request.valid = true;
                                m_rx_state = eRxStateWaitForProcess;
                                m_request_received = true;
                            }
                            else
                            {
                                reset_rx();
                            }
                        }
                        else
                        {
                            reset_rx();
                        }
                    }

                    m_crc_bytes_received++;
                    i+=1;
                    break;
                }

                default:
                    break;
            }
        }
    }

    Response* CommHandler::prepare_response()
    {
        m_active_response.reset();
        return &m_active_response;
    }

    bool CommHandler::send_response(Response* response)
    {
        if (m_enabled == false)
        {
            return false;
        }

        if (m_state != eStateIdle)
        {
            m_tx_error = eTxErrorBusy;
            return false; // Half duplex comm. Discard data;
        }

        if (response->data_length > SCRUTINY_BUFFER_SIZE)
        {
            reset_tx();
            m_tx_error = eTxErrorOverflow;
            return false;
        }

        m_active_response.command_id = response->command_id | 0x80;
        m_active_response.subfunction_id = response->subfunction_id;
        m_active_response.response_code = response->response_code;
        m_active_response.data_length = response->data_length;
        m_active_response.data = response->data;

        add_crc(&m_active_response);

        // cmd8 + subfn8 + code8 + len16 + data + crc32
        m_nbytes_to_send = 1 + 1 + 1 + 2 + m_active_response.data_length + 4;

        m_state = eStateTransmitting;
        return true;
    }
    
    uint32_t CommHandler::pop_data(uint8_t* buffer, uint32_t len)
    {
        if (m_state != eStateTransmitting)
        {
            return 0;
        }

        const uint32_t nbytes_to_send = m_nbytes_to_send - m_nbytes_sent;
        uint32_t i=0;
        
        if (len >nbytes_to_send)
        {
            len = nbytes_to_send;
        }

        while (m_nbytes_sent < 5 && i<len)
        {
            if (m_nbytes_sent == 0)
            {
                buffer[i] = m_active_response.command_id;
            }
            else if (m_nbytes_sent == 1)
            {
                buffer[i] = m_active_response.subfunction_id;
            }
            else if (m_nbytes_sent == 2)
            {
                buffer[i] = m_active_response.response_code;
            }
            else if (m_nbytes_sent == 3)
            {
                buffer[i] = (m_active_response.data_length >> 8) & 0xFF;
            }
            else if (m_nbytes_sent == 4)
            {
                buffer[i] = m_active_response.data_length & 0xFF;
            }

            i++;
            m_nbytes_sent += 1;
        }
        
        int32_t remaining_data_bytes = static_cast<int32_t>(m_active_response.data_length) - (static_cast<int32_t>(m_nbytes_sent) - 5);
        if (remaining_data_bytes < 0)
        {
            remaining_data_bytes = 0;
        }

        uint32_t data_bytes_to_copy = static_cast<uint32_t>(remaining_data_bytes);
        if (data_bytes_to_copy > len-i)
        {
            data_bytes_to_copy = len-i;
        }

        std::memcpy(&buffer[i], &m_active_response.data[m_active_response.data_length - remaining_data_bytes], data_bytes_to_copy);

        i += data_bytes_to_copy;
        m_nbytes_sent += data_bytes_to_copy;

        const uint32_t crc_position = m_active_response.data_length + 5;
        while (i < len)
        {
            if (m_nbytes_sent == crc_position)
            {
                buffer[i] = (m_active_response.crc >> 24) & 0xFF;
            }
            else if (m_nbytes_sent == crc_position + 1)
            {
                buffer[i] = (m_active_response.crc >> 16) & 0xFF;
            }
            else if (m_nbytes_sent == crc_position + 2)
            {
                buffer[i] = (m_active_response.crc >> 8) & 0xFF;
            }
            else if (m_nbytes_sent == crc_position + 3)
            {
                buffer[i] = (m_active_response.crc >> 0) & 0xFF;
            }
            else
            {
                break;  // Should never go here.
            }
            m_nbytes_sent++;
            i++;
        }

        if (m_nbytes_sent >= m_nbytes_to_send)
        {
            reset_tx();
        }

        return i;
    }

    // Check if the last request received is a valid "Comm Discover request". If yes, enable comm (allow responses)
    bool CommHandler::check_must_enable()
    {
        if (m_active_request.command_id != eCmdCommControl)
        {
            return false;
        }

        if (m_active_request.subfunction_id != CommControl::eSubfnDiscover)
        {
            return false;
        }

        if (m_active_request.data_length < sizeof(CommControl::DISCOVER_MAGIC))
        {   
            return false;
        }

        if (std::memcmp(CommControl::DISCOVER_MAGIC, m_active_request.data, sizeof(CommControl::DISCOVER_MAGIC)) != 0)
        {
            return false;
        }

        return true;
    }

    
    uint32_t CommHandler::data_to_send()
    {
        if (m_state != eStateTransmitting)
        {
            return 0;
        }

        return m_nbytes_to_send - m_nbytes_sent;
    }

    bool CommHandler::check_crc(const Request* req)
    {
        uint32_t crc = 0;
        uint8_t header_data[4];
        header_data[0] = req->command_id;
        header_data[1] = req->subfunction_id;
        header_data[2] = (req->data_length >> 8) & 0xFF; 
        header_data[3] = req->data_length & 0xFF;
        crc = crc32(header_data, sizeof(header_data));
        crc = crc32(req->data, req->data_length, crc);
        return (crc == req->crc);
    }

    void CommHandler::add_crc(Response* response)
    {
        if (response->data_length > SCRUTINY_BUFFER_SIZE)
            return;

        uint8_t header[5];
        header[0] = response->command_id;
        header[1] = response->subfunction_id;
        header[2] = response->response_code;
        header[3] = (response->data_length >> 8) & 0xFF;
        header[4] = response->data_length & 0xFF;

        uint32_t crc = scrutiny::crc32(header, sizeof(header));
        response->crc = scrutiny::crc32(response->data, response->data_length, crc);
    }

    void CommHandler::reset()
    {
        m_state = eStateIdle;
        std::memset(m_buffer, 0, SCRUTINY_BUFFER_SIZE);

        reset_rx();
        reset_tx();
    }

    void CommHandler::reset_rx()
    {
        m_active_request.reset();
        m_rx_state = eRxStateWaitForCommand;
        m_request_received = false;
        m_crc_bytes_received = 0;
        m_length_bytes_received = 0;
        m_data_bytes_received = 0;
        m_rx_error = eRxErrorNone;
        m_last_rx_timestamp = m_timebase->get_timestamp();

        if (m_state == eStateReceiving)
        {
            m_state = eStateIdle;
        }
    }

    void CommHandler::reset_tx()
    {
        m_active_response.reset();
        m_nbytes_to_send = 0;
        m_nbytes_sent = 0;
        m_tx_error = eTxErrorNone;

        if (m_state == eStateTransmitting)
        {
            m_state = eStateIdle;
        }
    }

}   // namespace Protocol
}   // namespace scrutiny