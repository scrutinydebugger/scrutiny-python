#include "protocol/scrutiny_protocol.h"
#include <cstring>
#include <iostream>

namespace scrutiny
{
    Protocol::Protocol(uint8_t major, uint8_t minor, Timebase* timebase)
    {
        m_version.major = major;
        m_version.minor = minor;
        m_timebase = timebase;

        reset();
    }

    uint8_t Protocol::process_data(uint8_t* data, uint32_t len)
    {
        uint32_t i = 0;

        while (i < len && !m_request_received && m_rx_state != eRxStateError)
        {
            switch (m_rx_state)
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
                        m_rx_state = eRxStateWaitForProcess;
                        m_request_received = true;
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


    void Protocol::reset()
    {
        m_active_request.reset();
        m_active_request.data = m_rx_buffer;
        m_rx_state = eRxStateWaitForCommand;
        m_request_received = false;
        m_crc_bytes_received = 0;
        m_length_bytes_received = 0;
        m_data_bytes_received = 0;
        m_rx_error = eRxErrorNone;
        std::memset(m_rx_buffer, 0, SCRUTINY_RX_BUFFER_SIZE);
    }

    void Protocol::process_request(Request* req)
    {
        
    }
}