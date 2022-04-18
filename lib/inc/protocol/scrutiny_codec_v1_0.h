//    scrutiny_codec_v1_0.h
//        Definitions of encode/decode functions for the scrutiny protocol V1.0
//
//   - License : MIT - See LICENSE file.
//   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
//
//   Copyright (c) 2021-2022 scrutinydebugger

#ifndef ___SCRUTINY_CODEC_V1_0___
#define ___SCRUTINY_CODEC_V1_0___

#include <cstdint>
#include "scrutiny_protocol_definitions.h"
#include "scrutiny_software_id.h"

namespace scrutiny
{
	namespace protocol
	{
		class ReadMemoryBlocksRequestParser
		{
		public:
			ReadMemoryBlocksRequestParser();
			void init(const Request* request);
			void next(MemoryBlock* memblock);
			inline bool finished() { return m_finished; };
			inline bool is_valid() { return !m_invalid; };
			inline uint32_t required_tx_buffer_size() { return m_required_tx_buffer_size; }
			void reset();

		protected:
			void validate();

			uint8_t* m_buffer;
			uint32_t m_bytes_read;
			uint32_t m_size_limit;
			uint32_t m_required_tx_buffer_size;
			bool m_finished;
			bool m_invalid;
		};

		class ReadMemoryBlocksResponseEncoder
		{
		public:
			ReadMemoryBlocksResponseEncoder();
			void init(Response* response, const uint32_t max_size);
			void write(MemoryBlock* memblock);
			inline bool overflow() { return m_overflow; };
			void reset();

		protected:
			uint8_t* m_buffer;
			Response* m_response;
			uint32_t m_cursor;
			uint32_t m_size_limit;
			bool m_overflow;
		};

		class WriteMemoryBlocksRequestParser
		{
		public:
			WriteMemoryBlocksRequestParser();
			void init(const Request* request);
			void next(MemoryBlock* memblock);
			inline bool finished() { return m_finished; };
			inline bool is_valid() { return !m_invalid; };
			inline uint32_t required_tx_buffer_size() { return m_required_tx_buffer_size; }
			void reset();

		protected:
			void validate();

			uint8_t* m_buffer;
			uint32_t m_bytes_read;
			uint32_t m_size_limit;
			uint32_t m_required_tx_buffer_size;
			bool m_finished;
			bool m_invalid;
		};

		class WriteMemoryBlocksResponseEncoder
		{
		public:
			WriteMemoryBlocksResponseEncoder();
			void init(Response* response, uint32_t max_size);
			void write(MemoryBlock* memblock);
			inline bool overflow() { return m_overflow; };
			void reset();

		protected:
			uint8_t* m_buffer;
			Response* m_response;
			uint32_t m_cursor;
			uint32_t m_size_limit;
			bool m_overflow;
		};

		namespace ResponseData
		{
			namespace GetInfo
			{
				struct GetProtocolVersion
				{
					uint8_t major;
					uint8_t minor;
				};

				struct GetSupportedFeatures
				{
					bool memory_read;
					bool memory_write;
					bool datalog_acquire;
					bool user_command;
				};

				struct GetSpecialMemoryRegionCount
				{
					uint8_t nbr_readonly_region;
					uint8_t nbr_forbidden_region;
				};

				struct GetSpecialMemoryRegionLocation
				{
					uint8_t region_type;
					uint8_t region_index;
					uint64_t start;
					uint64_t end;
				};
			}

			namespace CommControl
			{
				struct Heartbeat
				{
					uint32_t session_id;
					uint16_t challenge_response;
				};
				struct GetParams
				{
					uint16_t data_rx_buffer_size;
					uint16_t data_tx_buffer_size;
					uint32_t max_bitrate;
					uint32_t comm_rx_timeout;
					uint32_t heartbeat_timeout;
					uint8_t address_size;
				};
				struct Connect
				{
					uint8_t magic[sizeof(protocol::CommControl::CONNECT_MAGIC)];
					uint32_t session_id;
				};
			}
		}


		namespace RequestData
		{
			namespace GetInfo
			{
				struct GetSpecialMemoryRegionLocation
				{
					uint8_t region_type;
					uint8_t region_index;
				};
			}

			namespace CommControl
			{
				struct Discover
				{
					uint8_t magic[sizeof(protocol::CommControl::DISCOVER_MAGIC)];
				};

				struct Heartbeat
				{
					uint32_t session_id;
					uint16_t challenge;
				};

				struct Connect
				{
					uint8_t magic[sizeof(protocol::CommControl::CONNECT_MAGIC)];
				};

				struct Disconnect
				{
					uint32_t session_id;
				};
			} 
		}


		class CodecV1_0
		{
		public:

			ResponseCode encode_response_protocol_version(const ResponseData::GetInfo::GetProtocolVersion* response_data, Response* response);
			ResponseCode encode_response_software_id(Response* response);
			ResponseCode encode_response_special_memory_region_count(const ResponseData::GetInfo::GetSpecialMemoryRegionCount* response_data, Response* response);
			ResponseCode encode_response_special_memory_region_location(const ResponseData::GetInfo::GetSpecialMemoryRegionLocation* response_data, Response* response);
			ResponseCode encode_response_supported_features(const ResponseData::GetInfo::GetSupportedFeatures* response_data, Response* response);

			ResponseCode encode_response_comm_discover( Response* response);
			ResponseCode encode_response_comm_heartbeat(const ResponseData::CommControl::Heartbeat* response_data, Response* response);
			ResponseCode encode_response_comm_get_params(const ResponseData::CommControl::GetParams* response_data, Response* response);
			ResponseCode encode_response_comm_connect(const ResponseData::CommControl::Connect* response_data, Response* response);


			ResponseCode decode_request_get_special_memory_region_location(const Request* request, RequestData::GetInfo::GetSpecialMemoryRegionLocation* request_data);

			ResponseCode decode_request_comm_discover(const Request* request, RequestData::CommControl::Discover* request_data);
			ResponseCode decode_request_comm_heartbeat(const Request* request, RequestData::CommControl::Heartbeat* request_data);
			ResponseCode decode_request_comm_connect(const Request* request, RequestData::CommControl::Connect* request_data);
			ResponseCode decode_request_comm_disconnect(const Request* request, RequestData::CommControl::Disconnect* request_data);

			ReadMemoryBlocksRequestParser* decode_request_memory_control_read(const Request* request);
			ReadMemoryBlocksResponseEncoder* encode_response_memory_control_read(Response* response, uint32_t max_size);

			WriteMemoryBlocksRequestParser* decode_request_memory_control_write(const Request* request);
			WriteMemoryBlocksResponseEncoder* encode_response_memory_control_write(Response* response, uint32_t max_size);

		protected:
			ReadMemoryBlocksRequestParser m_memory_control_read_request_parser;
			ReadMemoryBlocksResponseEncoder m_memory_control_read_response_encoder;
			WriteMemoryBlocksRequestParser m_memory_control_write_request_parser;
			WriteMemoryBlocksResponseEncoder m_memory_control_write_response_encoder;
		};
	}
}
#endif // ___SCRUTINY_CODEC_V1_0___