//    scrutiny_comm_handler.cpp
//        Manage the tranport-ish layer of the communication protocol. Converts Request/Response
//        to byte stream and validate CRC
//
//   - License : MIT - See LICENSE file.
//   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
//
//   Copyright (c) 2021-2022 scrutinydebugger

#include <cstring>

#include "protocol/scrutiny_comm_handler.h"
#include "scrutiny_crc.h"

namespace scrutiny
{
	namespace protocol
	{
		void CommHandler::init(Timebase* timebase)
		{
			m_timebase = timebase;

			m_active_request.data = m_rx_buffer;   // Half duplex comm. Share buffer
			m_active_response.data = m_tx_buffer;  // Half duplex comm. Share buffer

			reset();
		}

		void CommHandler::receive_data(uint8_t* data, uint32_t len)
		{
			uint32_t i = 0;

			if (m_enabled == false)
			{
				return;
			}

			if (m_state == State::Transmitting)
			{
				return; // Half duplex comm. Discard data;
			}

			// Handle rx timeouts. Start a new reception if no data for too long
			if (m_rx_state != RxFSMState::WaitForCommand && len != 0)
			{	
				if (m_timebase->has_expired(m_last_rx_timestamp, SCRUTINY_COMM_RX_TIMEOUT_US))
				{
					reset_rx();
					m_state = State::Idle;
				}
			}

			// Update rx timestamp
			if (len != 0)
			{
				m_last_rx_timestamp = m_timebase->get_timestamp();

				if (m_state == State::Idle)
				{
					m_state = State::Receiving;
				}
			}

			// Process each bytes
			while (i < len && !m_request_received && m_rx_state != RxFSMState::Error)
			{

				switch (m_rx_state) // FSM
				{
				case RxFSMState::WaitForCommand:
				{
					m_active_request.command_id = data[i] & 0x7F;
					m_rx_state = RxFSMState::WaitForSubfunction;
					i += 1;
					break;
				}

				case RxFSMState::WaitForSubfunction:
				{
					m_active_request.subfunction_id = data[i];
					m_rx_state = RxFSMState::WaitForLength;
					i += 1;
					break;
				}

				case RxFSMState::WaitForLength:
				{
					bool next_state = false;
					if (m_length_bytes_received == 0)
					{
						if ((len - i) >= 2)
						{
							m_active_request.data_length = (((uint16_t)data[i]) << 8) | ((uint16_t)data[i + 1]);
							m_length_bytes_received = 2;
							i += 2;
							next_state = true;
						}
						else
						{
							m_active_request.data_length = (((uint16_t)data[i]) << 8);
							m_length_bytes_received = 1;
							i += 1;
						}
					}
					else
					{
						m_active_request.data_length |= ((uint16_t)data[i]);
						m_length_bytes_received = 2;
						i += 1;
						next_state = true;
					}

					if (next_state)
					{
						if (m_active_request.data_length == 0)
						{
							m_rx_state = RxFSMState::WaitForCRC;
						}
						else
						{
							m_rx_state = RxFSMState::WaitForData;
						}
					}
					break;
				}

				case RxFSMState::WaitForData:
				{
					if (m_active_request.data_length > SCRUTINY_RX_BUFFER_SIZE)
					{
						m_rx_error = RxError::Overflow;
						m_rx_state = RxFSMState::Error;
						break;
					}

					const uint16_t available_bytes = static_cast<uint16_t>(len - i);
					const uint16_t missing_bytes = m_active_request.data_length - m_data_bytes_received;
					const uint16_t data_bytes_to_read = (available_bytes >= missing_bytes) ? missing_bytes : available_bytes;

					std::memcpy(&m_rx_buffer[m_data_bytes_received], &data[i], data_bytes_to_read);
					m_data_bytes_received += data_bytes_to_read;
					i += data_bytes_to_read;

					if (m_data_bytes_received >= m_active_request.data_length)
					{
						m_rx_state = RxFSMState::WaitForCRC;
					}

					break;
				}

				case RxFSMState::WaitForCRC:
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
						m_state = State::Idle;

						if (check_crc(&m_active_request))
						{
							process_active_request();
						}
						else
						{
							reset_rx();
						}
					}

					m_crc_bytes_received++;
					i += 1;
					break;
				}

				default:
					break;
				}
			}
		}

		void CommHandler::process_active_request()
		{
			bool must_process = false;
			if (m_session_active == false)
			{
				if (received_discover_request() || received_connect_request())    // Check if we received a valid discover message
				{
					must_process = true;
				}
			}
			else
			{
				must_process = true;
			}

			if (must_process)
			{
				m_rx_state = RxFSMState::WaitForProcess;
				m_request_received = true;
			}
			else
			{
				reset_rx();
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

			if (m_state != State::Idle)
			{
				m_tx_error = TxError::Busy;
				return false; // Half duplex comm. Discard data;
			}

			if (response->data_length > SCRUTINY_TX_BUFFER_SIZE)
			{
				reset_tx();
				m_tx_error = TxError::Overflow;
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

			m_state = State::Transmitting;
			return true;
		}

		uint32_t CommHandler::pop_data(uint8_t* buffer, uint32_t len)
		{
			if (m_state != State::Transmitting)
			{
				return 0;
			}

			const uint32_t nbytes_to_send = m_nbytes_to_send - m_nbytes_sent;
			uint32_t i = 0;

			if (len > nbytes_to_send)
			{
				len = nbytes_to_send;
			}

			while (m_nbytes_sent < 5 && i < len)
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
			if (data_bytes_to_copy > len - i)
			{
				data_bytes_to_copy = len - i;
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

		// Check if the last request received is a valid "Comm Discover request".
		bool CommHandler::received_discover_request()
		{
			if (m_active_request.command_id != static_cast<uint8_t>(CommandId::CommControl))
			{
				return false;
			}

			if (m_active_request.subfunction_id != static_cast<uint8_t>(CommControl::Subfunction::Discover))
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

		// Check if the last request received is a valid "Comm Discover request".
		bool CommHandler::received_connect_request()
		{
			if (m_active_request.command_id != static_cast<uint8_t>(CommandId::CommControl))
			{
				return false;
			}

			if (m_active_request.subfunction_id != static_cast<uint8_t>(CommControl::Subfunction::Connect))
			{
				return false;
			}

			return true;
		}

		void CommHandler::process()
		{
			if (m_session_active)
			{
				if (m_timebase->has_expired(m_heartbeat_timestamp, SCRUTINY_COMM_HEARTBEAT_TMEOUT_US))
				{
					reset();    // Disable and reset all internal vars
				}
			}
		}

		bool CommHandler::heartbeat(uint16_t challenge)
		{
			bool success = false;
			if (!m_session_active || !m_enabled)
			{
				return false;
			}

			if ((challenge != m_last_heartbeat_challenge || m_heartbeat_received == false))
			{
				m_heartbeat_received = true;
				m_heartbeat_timestamp = m_timebase->get_timestamp();
				m_last_heartbeat_challenge = challenge;
				success = true;
			}
			return success;
		}

		uint32_t CommHandler::data_to_send()
		{
			if (m_state != State::Transmitting)
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
			if (response->data_length > SCRUTINY_TX_BUFFER_SIZE)
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
			m_state = State::Idle;
			m_enabled = true;
			m_heartbeat_timestamp = m_timebase->get_timestamp();
			m_last_heartbeat_challenge = 0;
			m_heartbeat_received = false;
			m_session_id = 0;
			m_session_active = false;

			reset_rx();
			reset_tx();
		}

		void CommHandler::reset_rx()
		{
			m_active_request.reset();
			m_rx_state = RxFSMState::WaitForCommand;
			m_request_received = false;
			m_crc_bytes_received = 0;
			m_length_bytes_received = 0;
			m_data_bytes_received = 0;
			m_rx_error = RxError::None;
			m_last_rx_timestamp = m_timebase->get_timestamp();

			if (m_state == State::Receiving)
			{
				m_state = State::Idle;
			}
		}

		void CommHandler::reset_tx()
		{
			m_active_response.reset();
			m_nbytes_to_send = 0;
			m_nbytes_sent = 0;
			m_tx_error = TxError::None;

			if (m_state == State::Transmitting)
			{
				m_state = State::Idle;
			}
		}


		bool CommHandler::connect()
		{
			static uint32_t session_counter=0;	// todo : improve with prng
			if (!m_enabled)
			{
				return false;
			}

			if (m_session_active)
			{
				return false;
			}


			m_session_id = session_counter++;
			m_session_active = true;
			m_heartbeat_received = false;
			reset_rx();

			return true;
		}

		void CommHandler::disconnect()
		{
			m_session_id = 0;
			m_session_active = false;
			m_heartbeat_received = false;
			reset_rx();
			reset_tx();
		}


	}   // namespace protocol
}   // namespace scrutiny