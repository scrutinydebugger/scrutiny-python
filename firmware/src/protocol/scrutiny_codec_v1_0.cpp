#include "scrutiny_setup.h"
#include "scrutiny_codec_v1_0.h"
#include "scrutiny_software_id.h"
#include "scrutiny_protocol_tools.h"
#include <cstring>

#if defined(_MSC_VER)
#pragma warning(disable:4127)   // Get rid of constexpr always true condition warning.
#endif 

namespace scrutiny
{
	namespace Protocol
	{

		ReadMemoryBlocksRequestParser::ReadMemoryBlocksRequestParser() :
			m_buffer(NULL),
			m_bytes_read(0),
			m_size_limit(0),
			m_finished(false),
			m_invalid(false)
		{

		}
				
		void ReadMemoryBlocksRequestParser::init(Request* request)
		{
			m_buffer = request->data;
			m_size_limit = request->data_length;
			reset();
			validate();
		}

		void ReadMemoryBlocksRequestParser::validate()
		{
			constexpr unsigned int addr_size = sizeof(void*);
			uint32_t cursor = 0;
			uint16_t length;

			while (true)
			{
				if ( cursor + addr_size + 2 > m_size_limit)
				{
					m_invalid = true;
					return;
				}

				cursor += addr_size;
				length = decode_16_bits_big_endian(&m_buffer[cursor]);
				cursor += 2;

				if (cursor == m_size_limit)
				{
					break;
				}
			}
		}

		void ReadMemoryBlocksRequestParser::next(MemoryBlock* memblock)
		{
			constexpr unsigned int addr_size = sizeof(void*);
			uint16_t length;
			uint64_t addr;
			if (m_finished || m_invalid)
			{
				return;
			}

			if (m_bytes_read + addr_size + 2 > m_size_limit)
			{
				m_finished = true;
				m_invalid = true;
				return;
			}

			decode_address_big_endian(&m_buffer[m_bytes_read], &addr);
			m_bytes_read += addr_size;
			length = decode_16_bits_big_endian(&m_buffer[m_bytes_read]);
			m_bytes_read += 2;

			memblock->start_address = reinterpret_cast<uint8_t*>(addr);
			memblock->length = length;

			if (m_bytes_read == m_size_limit)
			{
				m_finished = true;
			}
		}

		void ReadMemoryBlocksRequestParser::reset()
		{
			m_bytes_read = 0;
			m_invalid = false;
			m_finished = false;
		}





		ReadMemoryBlocksResponseEncoder::ReadMemoryBlocksResponseEncoder()
		{

		}

		void ReadMemoryBlocksResponseEncoder::init(Response* response)
		{
			m_size_limit = SCRUTINY_TX_BUFFER_SIZE;	// todo : find a better way to bring this limit down to the codec.
			m_buffer = response->data;
			m_response = response;
			reset();
		}

		void ReadMemoryBlocksResponseEncoder::write(MemoryBlock* memblock)
		{
			constexpr unsigned int addr_size = sizeof(void*);

			if (m_cursor + addr_size + 2 + memblock->length > m_size_limit)
			{
				m_overflow = true;
				return;
			}

			encode_address_big_endian(&m_buffer[m_cursor], memblock->start_address);
			m_cursor += addr_size;
			encode_16_bits_big_endian(memblock->length, &m_buffer[m_cursor]);
			m_cursor += 2;
			std::memcpy(&m_buffer[m_cursor], memblock->start_address, memblock->length);
			m_cursor += memblock->length;

			m_response->data_length = static_cast<uint16_t>(m_cursor);
		}

		void ReadMemoryBlocksResponseEncoder::reset()
		{
			m_cursor = 0;
			m_overflow = false;
		}


		

		// ===== Encoding =====
		ResponseCode CodecV1_0::encode_response_protocol_version(const ResponseData* response_data, Response* response)
		{
			constexpr uint16_t datalen = 2;

			if (datalen > SCRUTINY_TX_BUFFER_SIZE)
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

			if (datalen > SCRUTINY_TX_BUFFER_SIZE)
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

			if (datalen > SCRUTINY_TX_BUFFER_SIZE)
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
			constexpr uint16_t session_id_size = sizeof(response_data->comm_control.heartbeat.session_id);
			constexpr uint16_t challenge_response_size = sizeof(response_data->comm_control.heartbeat.challenge_response);
			constexpr uint16_t datalen = session_id_size + challenge_response_size;

			if (datalen > SCRUTINY_TX_BUFFER_SIZE)
			{
				return eResponseCode_FailureToProceed;
			}

			response->data_length = datalen;
			encode_32_bits_big_endian(response_data->comm_control.heartbeat.session_id, &response->data[0]);
			encode_16_bits_big_endian(response_data->comm_control.heartbeat.challenge_response, &response->data[4]);

			return eResponseCode_OK;
		}

		ResponseCode CodecV1_0::encode_response_comm_get_params(const ResponseData* response_data, Response* response)
		{
			constexpr uint16_t rx_buffer_size_len = sizeof(response_data->comm_control.get_params.data_rx_buffer_size);
			constexpr uint16_t tx_buffer_size_len = sizeof(response_data->comm_control.get_params.data_tx_buffer_size);
			constexpr uint16_t max_bitrate_size = sizeof(response_data->comm_control.get_params.max_bitrate);
			constexpr uint16_t heartbeat_timeout_size = sizeof(response_data->comm_control.get_params.heartbeat_timeout);
			constexpr uint16_t comm_rx_timeout_size = sizeof(response_data->comm_control.get_params.comm_rx_timeout);
			constexpr uint16_t datalen = rx_buffer_size_len + tx_buffer_size_len + max_bitrate_size + heartbeat_timeout_size + comm_rx_timeout_size;

			constexpr uint16_t rx_buffer_size_pos = 0;
			constexpr uint16_t tx_buffer_size_pos = rx_buffer_size_pos + rx_buffer_size_len;
			constexpr uint16_t max_bitrate_pos = tx_buffer_size_pos + tx_buffer_size_len;
			constexpr uint16_t heartbeat_timeout_pos = max_bitrate_pos + max_bitrate_size;
			constexpr uint16_t comm_rx_timeout_pos = heartbeat_timeout_pos + heartbeat_timeout_size;

			if (datalen > SCRUTINY_TX_BUFFER_SIZE)
			{
				return eResponseCode_FailureToProceed;
			}

			response->data_length = datalen;

			encode_16_bits_big_endian(response_data->comm_control.get_params.data_rx_buffer_size, &response->data[rx_buffer_size_pos]);
			encode_16_bits_big_endian(response_data->comm_control.get_params.data_tx_buffer_size, &response->data[tx_buffer_size_pos]);
			encode_32_bits_big_endian(response_data->comm_control.get_params.max_bitrate, &response->data[max_bitrate_pos]);
			encode_32_bits_big_endian(response_data->comm_control.get_params.heartbeat_timeout, &response->data[heartbeat_timeout_pos]);
			encode_32_bits_big_endian(response_data->comm_control.get_params.comm_rx_timeout, &response->data[comm_rx_timeout_pos]);

			return eResponseCode_OK;
		}

		ResponseCode CodecV1_0::encode_response_comm_connect(const ResponseData* response_data, Response* response)
		{
			constexpr uint16_t magic_size = sizeof(response_data->comm_control.connect.magic);
			constexpr uint16_t session_id_size = sizeof(response_data->comm_control.connect.session_id);
			constexpr uint16_t datalen = magic_size + session_id_size;

			if (sizeof(response_data->comm_control.connect.magic) != sizeof(CommControl::CONNECT_MAGIC))
			{
				return eResponseCode_FailureToProceed;
			}

			if (datalen > SCRUTINY_TX_BUFFER_SIZE)
			{
				return eResponseCode_FailureToProceed;
			}

			response->data_length = datalen;
			std::memcpy(&response->data[0], response_data->comm_control.connect.magic, magic_size);
			encode_32_bits_big_endian(response_data->comm_control.connect.session_id, &response->data[magic_size]);

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
			constexpr uint16_t session_id_size = sizeof(request_data->comm_control.heartbeat.session_id);
			constexpr uint16_t challenge_size = sizeof(request_data->comm_control.heartbeat.challenge);
			constexpr uint16_t datalen = session_id_size + challenge_size;

			if (request->data_length != datalen)
			{
				return eResponseCode_InvalidRequest;
			}

			request_data->comm_control.heartbeat.session_id = decode_32_bits_big_endian(&request->data[0]);
			request_data->comm_control.heartbeat.challenge = decode_16_bits_big_endian(&request->data[4]);

			return eResponseCode_OK;
		}

		ResponseCode CodecV1_0::decode_request_comm_connect(const Request* request, RequestData* request_data)
		{
			constexpr uint16_t magic_size = sizeof(CommControl::DISCOVER_MAGIC);
			constexpr uint16_t datalen = magic_size;

			if (request->data_length != datalen)
			{
				return eResponseCode_InvalidRequest;
			}

			std::memcpy(request_data->comm_control.connect.magic, request->data, magic_size);

			return eResponseCode_OK;
		}

		ResponseCode CodecV1_0::decode_request_comm_disconnect(const Request* request, RequestData* request_data)
		{
			constexpr uint16_t session_id_size = sizeof(request_data->comm_control.disconnect.session_id);
			constexpr uint16_t datalen = session_id_size;

			if (request->data_length != datalen)
			{
				return eResponseCode_InvalidRequest;
			}

			request_data->comm_control.disconnect.session_id = decode_32_bits_big_endian(&request->data[0]);
			return eResponseCode_OK;
		}

		ReadMemoryBlocksRequestParser* CodecV1_0::decode_request_memory_control_read(Request* request)
		{
			m_memory_control_read_request_parser.init(request);
			return &m_memory_control_read_request_parser;
		}

		ReadMemoryBlocksResponseEncoder* CodecV1_0::encode_response_memory_control_read(Response* response)
		{
			response->data_length = 0;
			m_memory_control_read_response_encoder.init(response);
			return &m_memory_control_read_response_encoder;
		}


	}
}