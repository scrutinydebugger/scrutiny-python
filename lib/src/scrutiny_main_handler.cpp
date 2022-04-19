//    scrutiny_main_handler.cpp
//        The main scrutiny class to be manipulated by the user.
//
//   - License : MIT - See LICENSE file.
//   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
//
//   Copyright (c) 2021-2022 scrutinydebugger

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

	void MainHandler::process(const uint32_t timestep_us)
	{
		m_timebase.step(timestep_us);
		m_comm_handler.process();

		if (m_comm_handler.request_received() && !m_processing_request)
		{
			m_processing_request = true;
			protocol::Response* response = m_comm_handler.prepare_response();
			process_request(m_comm_handler.get_request(), response);

			m_comm_handler.send_response(response);
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


	void MainHandler::process_request(const protocol::Request* request, protocol::Response* response)
	{
		protocol::ResponseCode code = protocol::ResponseCode::FailureToProceed;
		response->reset();

		response->command_id = request->command_id;
		response->subfunction_id = request->subfunction_id;

		switch (static_cast<protocol::CommandId>(request->command_id))
		{
			// ============= [GetInfo] ============
		case protocol::CommandId::GetInfo:
			code = process_get_info(request, response);
			break;

			// ============= [CommControl] ============
		case protocol::CommandId::CommControl:
			code = process_comm_control(request, response);
			break;

			// ============= [MemoryControl] ============
		case protocol::CommandId::MemoryControl:
			code = process_memory_control(request, response);
			break;

			// ============= [DataLogControl] ===========
		case protocol::CommandId::DataLogControl:
			break;

			// ============= [UserCommand] ===========
		case protocol::CommandId::UserCommand:
			code = process_user_command(request, response);
			break;

			// ============================================
		default:
			code = protocol::ResponseCode::UnsupportedFeature;
			break;
		}

		response->response_code = static_cast<uint8_t>(code);
		if (code != protocol::ResponseCode::OK)
		{
			response->data_length = 0;
		}
	}


	// ============= [GetInfo] ============
	protocol::ResponseCode MainHandler::process_get_info(const protocol::Request* request, protocol::Response* response)
	{
		union
		{
			protocol::ResponseData::GetInfo::GetProtocolVersion get_protocol_version;
			protocol::ResponseData::GetInfo::GetSpecialMemoryRegionCount get_special_memory_region_count;
			protocol::ResponseData::GetInfo::GetSpecialMemoryRegionLocation get_special_memory_region_location;
			protocol::ResponseData::GetInfo::GetSupportedFeatures get_supproted_features;
		} response_data;

		union
		{
			protocol::RequestData::GetInfo::GetSpecialMemoryRegionLocation get_special_memory_region_location;
		} request_data;

		protocol::ResponseCode code = protocol::ResponseCode::FailureToProceed;

		switch (static_cast<protocol::GetInfo::Subfunction>(request->subfunction_id))
		{
			// =========== [GetprotocolVersion] ==========
		case protocol::GetInfo::Subfunction::GetprotocolVersion:
			response_data.get_protocol_version.major = SCRUTINY_PROTOCOL_VERSION_MAJOR(SCRUTINY_ACTUAL_PROTOCOL_VERSION);
			response_data.get_protocol_version.minor = SCRUTINY_PROTOCOL_VERSION_MINOR(SCRUTINY_ACTUAL_PROTOCOL_VERSION);
			code = m_codec.encode_response_protocol_version(&response_data.get_protocol_version, response);
			break;

			// =========== [GetSoftwareID] ==========
		case protocol::GetInfo::Subfunction::GetSoftwareId:
			code = m_codec.encode_response_software_id(response);
			break;

			// =========== [GetSupportedFeatures] ==========
		case protocol::GetInfo::Subfunction::GetSupportedFeatures:
			// TODO : Make this configurable.  Memory read/write should be disablable. Datalogging available only if configured. User command if a callback is given.
			response_data.get_supproted_features.memory_read = true;	
			response_data.get_supproted_features.memory_write = true;
			response_data.get_supproted_features.datalog_acquire = false;
			response_data.get_supproted_features.user_command = false;

			code = m_codec.encode_response_supported_features(&response_data.get_supproted_features, response);
			break;

			// =========== [GetSpecialMemoryRegionCount] ==========
		case protocol::GetInfo::Subfunction::GetSpecialMemoryRegionCount:

			response_data.get_special_memory_region_count.nbr_readonly_region = m_config.readonly_ranges_count();
			response_data.get_special_memory_region_count.nbr_forbidden_region = m_config.forbidden_ranges_count();

			code = m_codec.encode_response_special_memory_region_count(&response_data.get_special_memory_region_count, response);

			break;

			// =========== [GetSpecialMemoryLocation] ==========
		case protocol::GetInfo::Subfunction::GetSpecialMemoryLocation:

			code = m_codec.decode_request_get_special_memory_region_location(request, &request_data.get_special_memory_region_location);
			if (code != protocol::ResponseCode::OK)
			{
				break;
			}

			if (static_cast<protocol::GetInfo::MemoryRegionType>(request_data.get_special_memory_region_location.region_type) == protocol::GetInfo::MemoryRegionType::ReadOnly)
			{
				if (request_data.get_special_memory_region_location.region_index >= m_config.readonly_ranges_count())
				{
					code = protocol::ResponseCode::FailureToProceed;
					break;
				}

				if (!m_config.readonly_ranges()[request_data.get_special_memory_region_location.region_index].set)
				{
					code = protocol::ResponseCode::FailureToProceed;
					break;
				}

				response_data.get_special_memory_region_location.start = m_config.readonly_ranges()[request_data.get_special_memory_region_location.region_index].start;
				response_data.get_special_memory_region_location.end = m_config.readonly_ranges()[request_data.get_special_memory_region_location.region_index].end;
			}
			else if (static_cast<protocol::GetInfo::MemoryRegionType>(request_data.get_special_memory_region_location.region_type) == protocol::GetInfo::MemoryRegionType::Forbidden)
			{
				if (request_data.get_special_memory_region_location.region_index >= m_config.forbidden_ranges_count())
				{
					code = protocol::ResponseCode::FailureToProceed;
					break;
				}

				if (!m_config.forbidden_ranges()[request_data.get_special_memory_region_location.region_index].set)
				{
					code = protocol::ResponseCode::FailureToProceed;
					break;
				}

				response_data.get_special_memory_region_location.start = m_config.forbidden_ranges()[request_data.get_special_memory_region_location.region_index].start;
				response_data.get_special_memory_region_location.end = m_config.forbidden_ranges()[request_data.get_special_memory_region_location.region_index].end;
			}
			else
			{
				code = protocol::ResponseCode::InvalidRequest;
				break;
			}

			response_data.get_special_memory_region_location.region_type = request_data.get_special_memory_region_location.region_type;
			response_data.get_special_memory_region_location.region_index = request_data.get_special_memory_region_location.region_index;

			code = m_codec.encode_response_special_memory_region_location(&response_data.get_special_memory_region_location, response);
			break;

			// =================================
		default:
			code = protocol::ResponseCode::UnsupportedFeature;
			break;
		}

		return code;
	}

	// ============= [CommControl] ============
	protocol::ResponseCode MainHandler::process_comm_control(const protocol::Request* request, protocol::Response* response)
	{
		
		union
		{
			protocol::ResponseData::CommControl::Connect connect;
			protocol::ResponseData::CommControl::Discover discover;
			protocol::ResponseData::CommControl::GetParams get_params;
			protocol::ResponseData::CommControl::Heartbeat heartbeat;
		}response_data;

		union
		{
			protocol::RequestData::CommControl::Connect connect;
			protocol::RequestData::CommControl::Discover discover;
			protocol::RequestData::CommControl::Disconnect disconnect;
			protocol::RequestData::CommControl::Heartbeat heartbeat;
		}request_data;

		protocol::ResponseCode code = protocol::ResponseCode::FailureToProceed;

		switch (static_cast<protocol::CommControl::Subfunction>(request->subfunction_id))
		{
			// =========== [Discover] ==========
		case protocol::CommControl::Subfunction::Discover:
			code = m_codec.decode_request_comm_discover(request, &request_data.discover);
			if (code != protocol::ResponseCode::OK)
				break;

			// Magic validation is done by the codec.
			response_data.discover.display_name = m_config.display_name();
			code = m_codec.encode_response_comm_discover(response, &response_data.discover);
			break;

			// =========== [Heartbeat] ==========
		case protocol::CommControl::Subfunction::Heartbeat:
			code = m_codec.decode_request_comm_heartbeat(request, &request_data.heartbeat);
			if (code != protocol::ResponseCode::OK)
				break;

			if (request_data.heartbeat.session_id != m_comm_handler.get_session_id())
			{
				code = protocol::ResponseCode::InvalidRequest;
				break;
			}

			bool success;
			success = m_comm_handler.heartbeat(request_data.heartbeat.challenge);
			if (!success)
			{
				code = protocol::ResponseCode::InvalidRequest;
				break;
			}

			response_data.heartbeat.session_id = m_comm_handler.get_session_id();
			response_data.heartbeat.challenge_response = ~request_data.heartbeat.challenge;

			code = m_codec.encode_response_comm_heartbeat(&response_data.heartbeat, response);
			break;

			// =========== [GetParams] ==========
		case protocol::CommControl::Subfunction::GetParams:
			response_data.get_params.data_tx_buffer_size = SCRUTINY_TX_BUFFER_SIZE;
			response_data.get_params.data_rx_buffer_size = SCRUTINY_RX_BUFFER_SIZE;
			response_data.get_params.max_bitrate = m_config.max_bitrate;
			response_data.get_params.comm_rx_timeout = SCRUTINY_COMM_RX_TIMEOUT_US;
			response_data.get_params.heartbeat_timeout = SCRUTINY_COMM_HEARTBEAT_TMEOUT_US;
			response_data.get_params.address_size = sizeof(void*);
			code = m_codec.encode_response_comm_get_params(&response_data.get_params, response);
			break;

			// =========== [Connect] ==========
		case protocol::CommControl::Subfunction::Connect:
			code = m_codec.decode_request_comm_connect(request, &request_data.connect);
			if (code != protocol::ResponseCode::OK)
			{
				break;
			}

			if (m_comm_handler.is_connected())
			{
				code = protocol::ResponseCode::Busy;
				break;
			}

			if (m_comm_handler.connect() == false)
			{
				code = protocol::ResponseCode::FailureToProceed;
				break;
			}

			response_data.connect.session_id = m_comm_handler.get_session_id();
			std::memcpy(response_data.connect.magic, protocol::CommControl::CONNECT_MAGIC, sizeof(protocol::CommControl::CONNECT_MAGIC));
			code = m_codec.encode_response_comm_connect(&response_data.connect, response);
			break;


			// =========== [Diconnect] ==========
		case protocol::CommControl::Subfunction::Disconnect:
			code = m_codec.decode_request_comm_disconnect(request, &request_data.disconnect);
			if (code != protocol::ResponseCode::OK)
				break;

			if (m_comm_handler.is_connected())
			{
				if (m_comm_handler.get_session_id() == request_data.disconnect.session_id)
				{
					m_disconnect_pending = true;
				}
				else
				{
					code = protocol::ResponseCode::InvalidRequest;
					break;
				}
			}

			// empty data
			code = protocol::ResponseCode::OK;
			break;

			// =================================
		default:
			code = protocol::ResponseCode::UnsupportedFeature;
			break;
		}

		return code;
	}


	protocol::ResponseCode MainHandler::process_memory_control(const protocol::Request* request, protocol::Response* response)
	{
		protocol::ResponseCode code = protocol::ResponseCode::FailureToProceed;
		protocol::MemoryBlock block;


		switch (static_cast<protocol::MemoryControl::Subfunction>(request->subfunction_id))
		{
			// =========== [Read] ==========
		case protocol::MemoryControl::Subfunction::Read:
			code = protocol::ResponseCode::OK;
			protocol::ReadMemoryBlocksRequestParser* readmem_parser;
			protocol::ReadMemoryBlocksResponseEncoder* readmem_encoder;
			readmem_parser = m_codec.decode_request_memory_control_read(request);
			readmem_encoder = m_codec.encode_response_memory_control_read(response, m_comm_handler.tx_buffer_size());
			if (!readmem_parser->is_valid())
			{
				code = protocol::ResponseCode::InvalidRequest;
				break;
			}

			if (readmem_parser->required_tx_buffer_size() > m_comm_handler.tx_buffer_size())
			{
				code = protocol::ResponseCode::Overflow;
				break;
			}

			while (!readmem_parser->finished())
			{
				readmem_parser->next(&block);

				if (!readmem_parser->is_valid())
				{
					code = protocol::ResponseCode::InvalidRequest;
					break;
				}

				if (touches_forbidden_region(&block))
				{
					code = protocol::ResponseCode::Forbidden;
					break;
				}

				readmem_encoder->write(&block);
				// We don't check overflow here as we rely on the request parser to be right on the required buffer size.
			}
			break;


			// =========== [Write] ==========
		case protocol::MemoryControl::Subfunction::Write:
			code = protocol::ResponseCode::OK;
			protocol::WriteMemoryBlocksRequestParser* writemem_parser;
			protocol::WriteMemoryBlocksResponseEncoder* writemem_encoder;
			writemem_parser = m_codec.decode_request_memory_control_write(request);
			writemem_encoder = m_codec.encode_response_memory_control_write(response, m_comm_handler.tx_buffer_size());
			if (!writemem_parser->is_valid())
			{
				code = protocol::ResponseCode::InvalidRequest;
				break;
			}

			if (writemem_parser->required_tx_buffer_size() > m_comm_handler.tx_buffer_size())
			{
				code = protocol::ResponseCode::Overflow;
				break;
			}

			while (!writemem_parser->finished())
			{
				writemem_parser->next(&block);

				if (!writemem_parser->is_valid())
				{
					code = protocol::ResponseCode::InvalidRequest;
					break;
				}

				if (touches_forbidden_region(&block))
				{
					code = protocol::ResponseCode::Forbidden;
					break;
				}

				if (touches_readonly_region(&block))
				{
					code = protocol::ResponseCode::Forbidden;
					break;
				}

				writemem_encoder->write(&block);
				// We don't check overflow here as we rely on the request parser to be right on the required buffer size.

				std::memcpy(block.start_address, block.source_data, block.length);
			}
			break;
			// =================================
		default:
			code = protocol::ResponseCode::UnsupportedFeature;
			break;
		}

		return code;
	}


	bool MainHandler::touches_forbidden_region(const protocol::MemoryBlock* block)
	{
		const uint64_t block_start = reinterpret_cast<uint64_t>(block->start_address);
		const uint64_t block_end = block_start + block->length;
		for (unsigned int i = 0; i < m_config.forbidden_ranges_max(); i++)
		{
			const AddressRange& range = m_config.forbidden_ranges()[i];
			if (range.set)	// We make assumption here that ranges are assigned squentially, which is the case
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

	bool MainHandler::touches_readonly_region(const protocol::MemoryBlock* block)
	{
		const uint64_t block_start = reinterpret_cast<uint64_t>(block->start_address);
		const uint64_t block_end = block_start + block->length;
		for (unsigned int i = 0; i < m_config.readonly_ranges_max(); i++)
		{
			const AddressRange& range = m_config.readonly_ranges()[i];
			if (range.set)	// We make assumption here that ranges are assigned squentially, which is the case
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

	protocol::ResponseCode MainHandler::process_user_command(const protocol::Request* request, protocol::Response* response)
	{
		protocol::ResponseCode code = protocol::ResponseCode::FailureToProceed;

		if (m_config.is_user_command_callback_set())
		{
			uint16_t response_data_length = 0;
			//caling user callback;
			m_config.user_command_callback(request->subfunction_id, request->data, request->data_length, response->data, &response_data_length, m_comm_handler.tx_buffer_size());
			if (response_data_length > m_comm_handler.tx_buffer_size())
			{
				code = protocol::ResponseCode::Overflow;
			}
			else
			{
				response->data_length = response_data_length;
				code = protocol::ResponseCode::OK;
			}
		}
		else
		{
			code = protocol::ResponseCode::UnsupportedFeature;
		}

		return code;
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