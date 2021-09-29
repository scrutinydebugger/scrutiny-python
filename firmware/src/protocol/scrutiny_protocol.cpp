#include <cstring>
#include <iostream>

#include "protocol/scrutiny_protocol.h"
#include "scrutiny_crc.h"

namespace scrutiny
{
    Protocol::Protocol(uint8_t major, uint8_t minor, Timebase* timebase)
    {
        m_version.major = major;
        m_version.minor = minor;
        m_timebase = timebase;

        m_active_request.data = m_rx_buffer;

        reset();
    }

    uint8_t Protocol::process_data(uint8_t* data, uint32_t len)
    {
        uint32_t i = 0;

        // Handle rx timeouts. Start a new reception if no data for too long
        if (m_rx_state != eRxStateWaitForCommand && len !=0 )
        {
            if (m_timebase->is_elapsed(m_last_rx_timestamp, SCRUTINY_COMM_TIMEOUT_US))
            {
                reset_rx();
            }
        }

        // Update rx timestamp
        if (len != 0)
        {
            m_last_rx_timestamp = m_timebase->get_timestamp();
        }

        // Process each bytes
        while (i < len && !m_request_received && m_rx_state != eRxStateError)
        {
            switch (m_rx_state) // FSM
            {
                case eRxStateWaitForCommand:
                {
                    m_active_request.command_id = data[i];
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
                    if (m_active_request.data_length > SCRUTINY_RX_BUFFER_SIZE)
                    {
                        m_rx_error = eRxErrorOverflow;
                        m_rx_state = eRxStateError;
                        break;
                    }

                    const uint16_t available_bytes = len-i;
                    const uint16_t missing_bytes = m_active_request.data_length - m_data_bytes_received;
                    const uint16_t data_bytes_to_read = (available_bytes >= missing_bytes) ? missing_bytes : available_bytes;

                    std::memcpy(&m_rx_buffer[m_data_bytes_received], &data[i], data_bytes_to_read);
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

                        if (check_crc(&m_active_request))
                        {
                            m_rx_state = eRxStateWaitForProcess;
                            m_request_received = true;
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


        return 0;
    }

    bool Protocol::check_crc(Request* req)
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


    void Protocol::reset()
    {
        std::memset(m_rx_buffer, 0, SCRUTINY_RX_BUFFER_SIZE);
        reset_rx();
    }

    void Protocol::reset_rx()
    {
        m_active_request.reset();
        m_rx_state = eRxStateWaitForCommand;
        m_request_received = false;
        m_crc_bytes_received = 0;
        m_length_bytes_received = 0;
        m_data_bytes_received = 0;
        m_rx_error = eRxErrorNone;
        m_last_rx_timestamp = m_timebase->get_timestamp();
    }
}