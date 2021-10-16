#include <cstring>

#include "scrutiny_setup.h"
#include "scrutiny_software_id.h"
#include "protocol/scrutiny_codec_v1_0.h"
#include "protocol/scrutiny_protocol_tools.h"

#if defined(_MSC_VER)
#pragma warning(disable:4127)   // Get rid of constexpr always true condition warning.
#endif 

namespace scrutiny
{
	namespace protocol
	{
		//==============================================================

		ReadMemoryBlocksRequestParser::ReadMemoryBlocksRequestParser() :
			m_buffer(NULL),
			m_bytes_read(0),
			m_size_limit(0),
			m_required_tx_buffer_size(0),
			m_finished(false),
			m_invalid(false)
		{

		}

		void ReadMemoryBlocksRequestParser::init(const Request* request)
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
				if (cursor + addr_size + 2 > m_size_limit)
				{
					m_invalid = true;
					return;
				}

				cursor += addr_size;
				length = decode_16_bits_big_endian(&m_buffer[cursor]);
				cursor += 2;

				m_required_tx_buffer_size += addr_size + 2 + length;

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
			m_required_tx_buffer_size = 0;
		}

		//==============================================================

		WriteMemoryBlocksRequestParser::WriteMemoryBlocksRequestParser() :
			m_buffer(NULL),
			m_bytes_read(0),
			m_size_limit(0),
			m_required_tx_buffer_size(0),
			m_finished(false),
			m_invalid(false)
		{

		}

		void WriteMemoryBlocksRequestParser::init(const Request* request)
		{
			m_buffer = request->data;
			m_size_limit = request->data_length;
			reset();
			validate();
		}

		void WriteMemoryBlocksRequestParser::validate()
		{
			constexpr unsigned int addr_size = sizeof(void*);
			uint32_t cursor = 0;
			uint16_t length;

			while (true)
			{
				if (cursor + addr_size + 2 > m_size_limit)
				{
					m_invalid = true;
					return;
				}

				cursor += addr_size;
				length = decode_16_bits_big_endian(&m_buffer[cursor]);
				cursor += 2;
				cursor += length;
				if (cursor > m_size_limit)
				{
					m_invalid = true;
					return;
				}

				m_required_tx_buffer_size += addr_size + 2;

				if (cursor == m_size_limit)
				{
					break;
				}
			}
		}

		void WriteMemoryBlocksRequestParser::next(MemoryBlock* memblock)
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

			if (m_bytes_read + length > m_size_limit)
			{
				m_invalid = true;
				m_finished = true;
				return;
			}

			memblock->start_address = reinterpret_cast<uint8_t*>(addr);
			memblock->source_data = reinterpret_cast<uint8_t*>(&m_buffer[m_bytes_read]);
			memblock->length = length;
			m_bytes_read += length;

			if (m_bytes_read == m_size_limit)
			{
				m_finished = true;
			}
		}

		void WriteMemoryBlocksRequestParser::reset()
		{
			m_bytes_read = 0;
			m_invalid = false;
			m_finished = false;
			m_required_tx_buffer_size = 0;
		}


		//==============================================================

		ReadMemoryBlocksResponseEncoder::ReadMemoryBlocksResponseEncoder() :
			m_buffer(NULL),
			m_response(NULL),
			m_cursor(0),
			m_size_limit(0),
			m_overflow(false)
		{

		}

		void ReadMemoryBlocksResponseEncoder::init(Response* response, const uint32_t max_size)
		{
			m_size_limit = max_size;
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

		//==============================================================


		WriteMemoryBlocksResponseEncoder::WriteMemoryBlocksResponseEncoder() :
			m_buffer(NULL),
			m_response(NULL),
			m_cursor(0),
			m_size_limit(0),
			m_overflow(false)
		{

		}

		void WriteMemoryBlocksResponseEncoder::init(Response* response, uint32_t max_size)
		{
			m_size_limit = max_size;
			m_buffer = response->data;
			m_response = response;
			reset();
		}

		void WriteMemoryBlocksResponseEncoder::write(MemoryBlock* memblock)
		{
			constexpr unsigned int addr_size = sizeof(void*);

			if (m_cursor + addr_size + 2 > m_size_limit)
			{
				m_overflow = true;
				return;
			}

			encode_address_big_endian(&m_buffer[m_cursor], memblock->start_address);
			m_cursor += addr_size;
			encode_16_bits_big_endian(memblock->length, &m_buffer[m_cursor]);
			m_cursor += 2;

			m_response->data_length = static_cast<uint16_t>(m_cursor);
		}

		void WriteMemoryBlocksResponseEncoder::reset()
		{
			m_cursor = 0;
			m_overflow = false;
		}

		//==============================================================


		// ===== Encoding =====
		ResponseCode CodecV1_0::encode_response_protocol_version(const ResponseData::GetInfo::GetProtocolVersion* response_data, Response* response)
		{
			constexpr uint16_t datalen = 2;

			static_assert(datalen <= SCRUTINY_TX_BUFFER_SIZE, "SCRUTINY_TX_BUFFER_SIZE too small");

			response->data_length = datalen;
			response->data[0] = response_data->major;
			response->data[1] = response_data->minor;

			return ResponseCode::OK;
		}

		ResponseCode CodecV1_0::encode_response_software_id(Response* response)
		{
			constexpr uint16_t datalen = sizeof(scrutiny::software_id);

			static_assert(datalen <= SCRUTINY_TX_BUFFER_SIZE, "SCRUTINY_TX_BUFFER_SIZE too small");

			response->data_length = datalen;
			std::memcpy(response->data, scrutiny::software_id, sizeof(scrutiny::software_id));
			return ResponseCode::OK;
		}

		ResponseCode CodecV1_0::encode_response_special_memory_region_count(const ResponseData::GetInfo::GetSpecialMemoryRegionCount* response_data, Response* response)
		{
			constexpr uint16_t readonly_region_count_size = sizeof(ResponseData::GetInfo::GetSpecialMemoryRegionCount::nbr_readonly_region);
			constexpr uint16_t forbidden_region_count_size = sizeof(ResponseData::GetInfo::GetSpecialMemoryRegionCount::nbr_forbidden_region);
			constexpr uint16_t datalen = readonly_region_count_size + forbidden_region_count_size;
			static_assert(datalen <= SCRUTINY_TX_BUFFER_SIZE, "SCRUTINY_TX_BUFFER_SIZE too small");

			response->data[0] = response_data->nbr_readonly_region;
			response->data[1] = response_data->nbr_forbidden_region;
			response->data_length = 2;
			return ResponseCode::OK;
		}

		ResponseCode CodecV1_0::encode_response_special_memory_region_location(const ResponseData::GetInfo::GetSpecialMemoryRegionLocation* response_data, Response* response)
		{
			constexpr unsigned int addr_size = sizeof(void*);
			constexpr uint16_t region_type_size = sizeof(ResponseData::GetInfo::GetSpecialMemoryRegionLocation::region_type);
			constexpr uint16_t region_index_size = sizeof(ResponseData::GetInfo::GetSpecialMemoryRegionLocation::region_index);
			constexpr uint16_t datalen = region_type_size + region_index_size + 2 * addr_size;

			static_assert(datalen <= SCRUTINY_TX_BUFFER_SIZE, "SCRUTINY_TX_BUFFER_SIZE too small");

			response->data[0] = static_cast<uint8_t>(response_data->region_type);
			response->data[1] = response_data->region_index;
			encode_address_big_endian(&response->data[2], response_data->start);
			encode_address_big_endian(&response->data[2 + addr_size], response_data->end);
			response->data_length = 1 + 1 + addr_size + addr_size;

			return ResponseCode::OK;
		}

		ResponseCode CodecV1_0::decode_request_get_special_memory_region_location(const Request* request, RequestData::GetInfo::GetSpecialMemoryRegionLocation* request_data)
		{
			request_data->region_type = request->data[0];
			request_data->region_index = request->data[1];
			return ResponseCode::OK;
		}

		ResponseCode CodecV1_0::encode_response_comm_discover(const ResponseData::CommControl::Discover* response_data, Response* response)
		{
			constexpr uint16_t magic_size = sizeof(CommControl::DISCOVER_MAGIC);
			constexpr uint16_t challenge_response_size = sizeof(response_data->challenge_response);
			constexpr uint16_t datalen = magic_size + challenge_response_size;

			static_assert (sizeof(response_data->magic) == sizeof(CommControl::DISCOVER_MAGIC), "Mismatch between codec definition and protocol constant.");
			static_assert(datalen <= SCRUTINY_TX_BUFFER_SIZE, "SCRUTINY_TX_BUFFER_SIZE too small");

			response->data_length = datalen;
			std::memcpy(&response->data[0], response_data->magic, magic_size);
			std::memcpy(&response->data[magic_size], response_data->challenge_response, challenge_response_size);

			return ResponseCode::OK;
		}

		ResponseCode CodecV1_0::encode_response_comm_heartbeat(const ResponseData::CommControl::Heartbeat* response_data, Response* response)
		{
			constexpr uint16_t session_id_size = sizeof(response_data->session_id);
			constexpr uint16_t challenge_response_size = sizeof(response_data->challenge_response);
			constexpr uint16_t datalen = session_id_size + challenge_response_size;

			static_assert(datalen <= SCRUTINY_TX_BUFFER_SIZE, "SCRUTINY_TX_BUFFER_SIZE too small");

			response->data_length = datalen;
			encode_32_bits_big_endian(response_data->session_id, &response->data[0]);
			encode_16_bits_big_endian(response_data->challenge_response, &response->data[4]);

			return ResponseCode::OK;
		}

		ResponseCode CodecV1_0::encode_response_comm_get_params(const ResponseData::CommControl::GetParams* response_data, Response* response)
		{
			constexpr uint16_t rx_buffer_size_len = sizeof(response_data->data_rx_buffer_size);
			constexpr uint16_t tx_buffer_size_len = sizeof(response_data->data_tx_buffer_size);
			constexpr uint16_t max_bitrate_size = sizeof(response_data->max_bitrate);
			constexpr uint16_t heartbeat_timeout_size = sizeof(response_data->heartbeat_timeout);
			constexpr uint16_t comm_rx_timeout_size = sizeof(response_data->comm_rx_timeout);
			constexpr uint16_t datalen = rx_buffer_size_len + tx_buffer_size_len + max_bitrate_size + heartbeat_timeout_size + comm_rx_timeout_size;

			constexpr uint16_t rx_buffer_size_pos = 0;
			constexpr uint16_t tx_buffer_size_pos = rx_buffer_size_pos + rx_buffer_size_len;
			constexpr uint16_t max_bitrate_pos = tx_buffer_size_pos + tx_buffer_size_len;
			constexpr uint16_t heartbeat_timeout_pos = max_bitrate_pos + max_bitrate_size;
			constexpr uint16_t comm_rx_timeout_pos = heartbeat_timeout_pos + heartbeat_timeout_size;

			static_assert(datalen <= SCRUTINY_TX_BUFFER_SIZE, "SCRUTINY_TX_BUFFER_SIZE too small");

			response->data_length = datalen;

			encode_16_bits_big_endian(response_data->data_rx_buffer_size, &response->data[rx_buffer_size_pos]);
			encode_16_bits_big_endian(response_data->data_tx_buffer_size, &response->data[tx_buffer_size_pos]);
			encode_32_bits_big_endian(response_data->max_bitrate, &response->data[max_bitrate_pos]);
			encode_32_bits_big_endian(response_data->heartbeat_timeout, &response->data[heartbeat_timeout_pos]);
			encode_32_bits_big_endian(response_data->comm_rx_timeout, &response->data[comm_rx_timeout_pos]);

			return ResponseCode::OK;
		}

		ResponseCode CodecV1_0::encode_response_comm_connect(const ResponseData::CommControl::Connect* response_data, Response* response)
		{
			constexpr uint16_t magic_size = sizeof(response_data->magic);
			constexpr uint16_t session_id_size = sizeof(response_data->session_id);
			constexpr uint16_t datalen = magic_size + session_id_size;

			static_assert (sizeof(response_data->magic) == sizeof(CommControl::CONNECT_MAGIC), "Mismatch between codec definition and protocol constant.");
			static_assert(datalen <= SCRUTINY_TX_BUFFER_SIZE, "SCRUTINY_TX_BUFFER_SIZE too small");

			response->data_length = datalen;
			std::memcpy(&response->data[0], response_data->magic, magic_size);
			encode_32_bits_big_endian(response_data->session_id, &response->data[magic_size]);

			return ResponseCode::OK;
		}



		// ===== Decoding =====
		ResponseCode CodecV1_0::decode_request_comm_discover(const Request* request, RequestData::CommControl::Discover* request_data)
		{
			constexpr uint16_t magic_size = sizeof(CommControl::DISCOVER_MAGIC);
			constexpr uint16_t challenge_size = sizeof(request_data->challenge);
			constexpr uint16_t datalen = magic_size + challenge_size;

			if (request->data_length != datalen)
			{
				return ResponseCode::InvalidRequest;
			}

			std::memcpy(request_data->magic, request->data, magic_size);
			std::memcpy(request_data->challenge, &request->data[magic_size], challenge_size);

			return ResponseCode::OK;
		}

		ResponseCode CodecV1_0::decode_request_comm_heartbeat(const Request* request, RequestData::CommControl::Heartbeat* request_data)
		{
			constexpr uint16_t session_id_size = sizeof(request_data->session_id);
			constexpr uint16_t challenge_size = sizeof(request_data->challenge);
			constexpr uint16_t datalen = session_id_size + challenge_size;

			if (request->data_length != datalen)
			{
				return ResponseCode::InvalidRequest;
			}

			request_data->session_id = decode_32_bits_big_endian(&request->data[0]);
			request_data->challenge = decode_16_bits_big_endian(&request->data[4]);

			return ResponseCode::OK;
		}

		ResponseCode CodecV1_0::decode_request_comm_connect(const Request* request, RequestData::CommControl::Connect* request_data)
		{
			constexpr uint16_t magic_size = sizeof(CommControl::DISCOVER_MAGIC);
			constexpr uint16_t datalen = magic_size;

			if (request->data_length != datalen)
			{
				return ResponseCode::InvalidRequest;
			}

			std::memcpy(request_data->magic, request->data, magic_size);

			return ResponseCode::OK;
		}

		ResponseCode CodecV1_0::decode_request_comm_disconnect(const Request* request, RequestData::CommControl::Disconnect* request_data)
		{
			constexpr uint16_t session_id_size = sizeof(request_data->session_id);
			constexpr uint16_t datalen = session_id_size;

			if (request->data_length != datalen)
			{
				return ResponseCode::InvalidRequest;
			}

			request_data->session_id = decode_32_bits_big_endian(&request->data[0]);
			return ResponseCode::OK;
		}

		ReadMemoryBlocksRequestParser* CodecV1_0::decode_request_memory_control_read(const Request* request)
		{
			m_memory_control_read_request_parser.init(request);
			return &m_memory_control_read_request_parser;
		}

		ReadMemoryBlocksResponseEncoder* CodecV1_0::encode_response_memory_control_read(Response* response, uint32_t max_size)
		{
			response->data_length = 0;
			m_memory_control_read_response_encoder.init(response, max_size);
			return &m_memory_control_read_response_encoder;
		}


		WriteMemoryBlocksRequestParser* CodecV1_0::decode_request_memory_control_write(const Request* request)
		{
			m_memory_control_write_request_parser.init(request);
			return &m_memory_control_write_request_parser;
		}

		WriteMemoryBlocksResponseEncoder* CodecV1_0::encode_response_memory_control_write(Response* response, uint32_t max_size)
		{
			response->data_length = 0;
			m_memory_control_write_response_encoder.init(response, max_size);
			return &m_memory_control_write_response_encoder;
		}
	}
}