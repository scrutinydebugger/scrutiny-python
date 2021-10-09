#include <cstring>

#include "scrutiny_main_handler.h"
#include "scrutiny_software_id.h"

namespace scrutiny
{


	void MainHandler::init(Config* config)
	{
		m_processing_request = false;
		m_disconnect_pending = false;
		m_comm_handler.init(&m_timebase);

		m_config.copy_from(config);
	}

	void MainHandler::process(uint32_t timestep_us)
	{
		m_timebase.step(timestep_us);
		m_comm_handler.process();

		if (m_comm_handler.request_received() && !m_processing_request)
		{
			m_processing_request = true;
			Protocol::Response* response = m_comm_handler.prepare_response();
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
				m_comm_handler.wait_next_request(); // Allow reception of next request
				m_processing_request = false;

				if (m_disconnect_pending)
				{
					m_comm_handler.disconnect();
					m_disconnect_pending = false;
				}
			}
		}
	}


	void MainHandler::process_request(Protocol::Request* request, Protocol::Response* response)
	{
		Protocol::ResponseCode code = Protocol::eResponseCode_FailureToProceed;
		response->reset();

		if (!request->valid)
			return;

		response->command_id = request->command_id;
		response->subfunction_id = request->subfunction_id;
		response->response_code = Protocol::eResponseCode_OK;
		response->valid = true;

		switch (request->command_id)
		{
			// ============= [GetInfo] ============
		case Protocol::eCmdGetInfo:
			code = process_get_info(request, response);
			break;

			// ============= [CommControl] ============
		case Protocol::eCmdCommControl:
			code = process_comm_control(request, response);
			break;

			// ============= [MemoryControl] ============
		case Protocol::eCmdMemoryControl:
			code = process_memory_control(request, response);
			break;

			// ============= [DataLogControl] ===========
		case Protocol::eCmdDataLogControl:
			break;

			// ============= [UserCommand] ===========
		case Protocol::eCmdUserCommand:
			break;

			// ============================================
		default:
			response->response_code = Protocol::eResponseCode_UnsupportedFeature;
			break;
		}

		response->response_code = static_cast<uint8_t>(code);
		if (code != Protocol::eResponseCode_OK)
		{
			response->data_length = 0;
		}
	}


	// ============= [GetInfo] ============
	Protocol::ResponseCode MainHandler::process_get_info(Protocol::Request* request, Protocol::Response* response)
	{
		Protocol::ResponseData response_data;
		Protocol::ResponseCode code = Protocol::eResponseCode_FailureToProceed;

		switch (request->subfunction_id)
		{
			// =========== [GetProtocolVersion] ==========
		case Protocol::GetInfo::eSubfnGetProtocolVersion:
			response_data.get_info.get_protocol_version.major = PROTOCOL_VERSION_MAJOR(ACTUAL_PROTOCOL_VERSION);
			response_data.get_info.get_protocol_version.minor = PROTOCOL_VERSION_MINOR(ACTUAL_PROTOCOL_VERSION);
			code = m_codec.encode_response_protocol_version(&response_data, response);
			break;

			// =========== [GetSoftwareID] ==========
		case Protocol::GetInfo::eSubfnGetSoftwareId:
			code = m_codec.encode_response_software_id(response);
			break;

			// =========== [GetSupportedFeatures] ==========
		case Protocol::GetInfo::eSubfnGetSupportedFeatures:
			break;

			// =================================
		default:
			response->response_code = Protocol::eResponseCode_UnsupportedFeature;
			break;
		}

		return code;
	}

	// ============= [CommControl] ============
	Protocol::ResponseCode MainHandler::process_comm_control(Protocol::Request* request, Protocol::Response* response)
	{
		Protocol::ResponseData response_data;
		Protocol::RequestData request_data;
		Protocol::ResponseCode code = Protocol::eResponseCode_FailureToProceed;

		switch (request->subfunction_id)
		{
			// =========== [Discover] ==========
		case Protocol::CommControl::eSubfnDiscover:
			code = m_codec.decode_request_comm_discover(request, &request_data);
			if (code != Protocol::eResponseCode_OK)
				break;

			std::memcpy(response_data.comm_control.discover.magic, Protocol::CommControl::DISCOVER_MAGIC, sizeof(Protocol::CommControl::DISCOVER_MAGIC));
			for (uint8_t i = 0; i < sizeof(request_data.comm_control.discover.challenge); i++)
			{
				response_data.comm_control.discover.challenge_response[i] = ~request_data.comm_control.discover.challenge[i];
			}

			code = m_codec.encode_response_comm_discover(&response_data, response);
			break;

			// =========== [Heartbeat] ==========
		case Protocol::CommControl::eSubfnHeartbeat:
			code = m_codec.decode_request_comm_heartbeat(request, &request_data);
			if (code != Protocol::eResponseCode_OK)
				break;

			if (request_data.comm_control.heartbeat.session_id != m_comm_handler.get_session_id())
			{
				code = Protocol::eResponseCode_InvalidRequest;
				break;
			}

			bool success;
			success = m_comm_handler.heartbeat(request_data.comm_control.heartbeat.challenge);
			if (!success)
			{
				code = Protocol::eResponseCode_InvalidRequest;
				break;
			}

			response_data.comm_control.heartbeat.session_id = m_comm_handler.get_session_id();
			response_data.comm_control.heartbeat.challenge_response = ~request_data.comm_control.heartbeat.challenge;

			code = m_codec.encode_response_comm_heartbeat(&response_data, response);
			break;

			// =========== [GetParams] ==========
		case Protocol::CommControl::eSubfnGetParams:
			response_data.comm_control.get_params.data_tx_buffer_size = SCRUTINY_TX_BUFFER_SIZE;
			response_data.comm_control.get_params.data_rx_buffer_size = SCRUTINY_RX_BUFFER_SIZE;
			response_data.comm_control.get_params.max_bitrate = m_config.get_max_bitrate();
			response_data.comm_control.get_params.comm_rx_timeout = SCRUTINY_COMM_RX_TIMEOUT_US;
			response_data.comm_control.get_params.heartbeat_timeout = SCRUTINY_COMM_HEARTBEAT_TMEOUT_US;
			code = m_codec.encode_response_comm_get_params(&response_data, response);
			break;

			// =========== [Connect] ==========
		case Protocol::CommControl::eSubfnConnect:
			code = m_codec.decode_request_comm_connect(request, &request_data);
			if (code != Protocol::eResponseCode_OK)
			{
				break;
			}

			if (m_comm_handler.is_connected())
			{
				code = Protocol::eResponseCode_Busy;
				break;
			}

			if (m_comm_handler.connect() == false)
			{
				code = Protocol::eResponseCode_FailureToProceed;
				break;
			}

			response_data.comm_control.connect.session_id = m_comm_handler.get_session_id();
			std::memcpy(response_data.comm_control.connect.magic, Protocol::CommControl::CONNECT_MAGIC, sizeof(Protocol::CommControl::CONNECT_MAGIC));
			code = m_codec.encode_response_comm_connect(&response_data, response);
			break;


			// =========== [Diconnect] ==========
		case Protocol::CommControl::eSubfnDisconnect:
			code = m_codec.decode_request_comm_disconnect(request, &request_data);
			if (code != Protocol::eResponseCode_OK)
				break;

			if (m_comm_handler.is_connected())
			{
				if (m_comm_handler.get_session_id() == request_data.comm_control.disconnect.session_id)
				{
					m_disconnect_pending = true;
				}
				else
				{
					code = Protocol::eResponseCode_InvalidRequest;
					break;
				}
			}

			// empty data
			code = Protocol::eResponseCode_OK;
			break;

			// =================================
		default:
			response->response_code = Protocol::eResponseCode_UnsupportedFeature;
			break;
		}

		return code;
	}


	Protocol::ResponseCode MainHandler::process_memory_control(Protocol::Request* request, Protocol::Response* response)
	{
		Protocol::ResponseCode code = Protocol::eResponseCode_FailureToProceed;
		Protocol::MemoryBlock block;


		switch (request->subfunction_id)
		{
		// =========== [Read] ==========
		case Protocol::MemoryControl::eSubfnRead:
			code = Protocol::eResponseCode_OK;
			Protocol::ReadMemoryBlocksRequestParser* readmem_parser;
			Protocol::ReadMemoryBlocksResponseEncoder* readmem_encoder;
			readmem_parser = m_codec.decode_request_memory_control_read(request);
			readmem_encoder = m_codec.encode_response_memory_control_read(response, m_comm_handler.tx_buffer_size());
			if (!readmem_parser->is_valid())
			{
				code = Protocol::eResponseCode_InvalidRequest;
				break;
			}

			while (!readmem_parser->finished())
			{
				readmem_parser->next(&block);

				if (!readmem_parser->is_valid())
				{
					code = Protocol::eResponseCode_InvalidRequest;
					break;
				}

				if (touches_forbidden_region(&block))
				{
					code = Protocol::eResponseCode_Forbidden;
					break;
				}

				readmem_encoder->write(&block);
				if (readmem_encoder->overflow())
				{
					code = Protocol::eResponseCode_Overflow;
					break;
				}
			}
			break;


			// =========== [Write] ==========
		case Protocol::MemoryControl::eSubfnWrite:
			code = Protocol::eResponseCode_OK;
			Protocol::WriteMemoryBlocksRequestParser* writemem_parser;
			Protocol::WriteMemoryBlocksResponseEncoder* writemem_encoder;
			writemem_parser = m_codec.decode_request_memory_control_write(request);
			writemem_encoder = m_codec.encode_response_memory_control_write(response, m_comm_handler.tx_buffer_size());
			if (!writemem_parser->is_valid())
			{
				code = Protocol::eResponseCode_InvalidRequest;
				break;
			}

			while (!writemem_parser->finished())
			{
				writemem_parser->next(&block);

				if (!writemem_parser->is_valid())
				{
					code = Protocol::eResponseCode_InvalidRequest;
					break;
				}

				if (touches_forbidden_region(&block))
				{
					code = Protocol::eResponseCode_Forbidden;
					break;
				}

				if (touches_readonly_region(&block))
				{
					code = Protocol::eResponseCode_Forbidden;
					break;
				}

				writemem_encoder->write(&block);
				if (writemem_encoder->overflow())
				{
					code = Protocol::eResponseCode_Overflow;
					break;
				}

				// All good, we can write memory.
				std::memcpy(block.start_address, block.source_data, block.length);
			}
			break;
			// =================================
		default:
			response->response_code = Protocol::eResponseCode_UnsupportedFeature;
			break;
		}

		return code;
	}


	bool MainHandler::touches_forbidden_region(Protocol::MemoryBlock* block)
	{
		const uint64_t block_start = reinterpret_cast<uint64_t>(block->start_address);
		const uint64_t block_end = block_start + block->length;
		for (unsigned int i = 0; i < SCRUTINY_FORBIDDEN_ADDRESS_RANGE_COUNT; i++)
		{
			const AddressRange& range = m_config.forbidden_ranges()[i];
			if (range.set)
			{
				if (block_start >= range.start && block_start <= range.end)
				{
					return true;
				}

				if (block_end >= range.start && block_end <= range.end)
				{
					return true;
				}
			}
			else
			{
				break;
			}
		}
		return false;
	}

	bool MainHandler::touches_readonly_region(Protocol::MemoryBlock* block)
	{
		const uint64_t block_start = reinterpret_cast<uint64_t>(block->start_address);
		const uint64_t block_end = block_start + block->length;
		for (unsigned int i = 0; i < SCRUTINY_READONLY_ADDRESS_RANGE_COUNT; i++)
		{
			const AddressRange& range = m_config.readonly_ranges()[i];
			if (range.set)
			{
				if (block_start >= range.start && block_start <= range.end)
				{
					return true;
				}

				if (block_end >= range.start && block_end <= range.end)
				{
					return true;
				}
			}
			else
			{
				break;
			}
		}
		return false;
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