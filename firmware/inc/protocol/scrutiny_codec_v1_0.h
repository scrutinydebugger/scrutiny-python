#ifndef ___SCRUTINY_CODEC_V1_0___
#define ___SCRUTINY_CODEC_V1_0___

#include <cstdint>
#include "scrutiny_protocol_definitions.h"


namespace scrutiny
{
	namespace Protocol
	{
		class ReadMemoryBlocksRequestParser
		{
		public:
			ReadMemoryBlocksRequestParser();
			void init(Request* request);
			void next(MemoryBlock* memblock);
			inline bool finished() { return m_finished; };
			inline bool is_valid() { return !m_invalid; };
			void reset();

		protected:
			void validate();

			uint8_t* m_buffer;
			uint32_t m_bytes_read;
			uint32_t m_size_limit;
			bool m_finished;
			bool m_invalid;
		};

		class ReadMemoryBlocksResponseEncoder
		{
		public:
			ReadMemoryBlocksResponseEncoder();
			void init(Response* response, uint32_t max_size);
			void write(MemoryBlock* memblock);
			inline bool overflow() { return m_overflow; };
			void reset();

		protected:
			void validate();

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
			void init(Request* request);
			void next(MemoryBlock* memblock);
			inline bool finished() { return m_finished; };
			inline bool is_valid() { return !m_invalid; };
			void reset();

		protected:
			void validate();

			uint8_t* m_buffer;
			uint32_t m_bytes_read;
			uint32_t m_size_limit;
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
			void validate();

			uint8_t* m_buffer;
			Response* m_response;
			uint32_t m_cursor;
			uint32_t m_size_limit;
			bool m_overflow;
		};

		union ResponseData
		{
			union
			{
				struct
				{
					uint8_t major;
					uint8_t minor;
				} get_protocol_version;

				struct
				{
					uint8_t temp;
				} get_supported_features;
			} get_info;

			union
			{
				struct
				{
					uint8_t magic[sizeof(CommControl::DISCOVER_MAGIC)];
					uint8_t challenge_response[4];
				} discover;
				struct
				{
					uint32_t session_id;
					uint16_t challenge_response;
				} heartbeat;
				struct
				{
					uint16_t data_rx_buffer_size;
					uint16_t data_tx_buffer_size;
					uint32_t max_bitrate;
					uint32_t comm_rx_timeout;
					uint32_t heartbeat_timeout;
				}get_params;
				struct
				{
					uint8_t magic[sizeof(CommControl::CONNECT_MAGIC)];
					uint32_t session_id;
				} connect;
			} comm_control;
		};


		union RequestData
		{
			union
			{
				struct
				{
					uint8_t magic[sizeof(CommControl::DISCOVER_MAGIC)];
					uint8_t challenge[4];
				} discover;

				struct
				{
					uint32_t session_id;
					uint16_t challenge;
				} heartbeat;

				struct
				{
					uint8_t magic[sizeof(CommControl::CONNECT_MAGIC)];
				} connect;

				struct
				{
					uint32_t session_id;
				} disconnect;
			} comm_control;
		};





		class CodecV1_0
		{
		public:

			ResponseCode encode_response_protocol_version(const ResponseData* response_data, Response* response);
			ResponseCode encode_response_software_id(Response* response);
			ResponseCode encode_response_comm_discover(const ResponseData* response_data, Response* response);
			ResponseCode encode_response_comm_heartbeat(const ResponseData* response_data, Response* response);
			ResponseCode encode_response_comm_get_params(const ResponseData* response_data, Response* response);
			ResponseCode encode_response_comm_connect(const ResponseData* response_data, Response* response);


			ResponseCode decode_request_comm_discover(const Request* request, RequestData* request_data);
			ResponseCode decode_request_comm_heartbeat(const Request* request, RequestData* request_data);
			ResponseCode decode_request_comm_connect(const Request* request, RequestData* request_data);
			ResponseCode decode_request_comm_disconnect(const Request* request, RequestData* request_data);

			ReadMemoryBlocksRequestParser* decode_request_memory_control_read(Request* request);
			ReadMemoryBlocksResponseEncoder* encode_response_memory_control_read(Response* response, uint32_t max_size);

			WriteMemoryBlocksRequestParser* decode_request_memory_control_write(Request* request);
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