//    scrutiny_main_handler.h
//        The main scrutiny class to be manipulated by the user
//
//   - License : MIT - See LICENSE file.
//   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
//
//   Copyright (c) 2021-2022 scrutinydebugger

#ifndef __SCRUTINY_HANDLER_H__
#define __SCRUTINY_HANDLER_H__

#include <cstdint>

#include "scrutiny_setup.h"
#include "scrutiny_loop_handler.h"
#include "scrutiny_timebase.h"
#include "protocol/scrutiny_protocol.h"
#include "scrutiny_config.h"

namespace scrutiny
{
	class MainHandler
	{

	public:
		void init(Config* config);
		//void process_loop(loop_id_t loop);
		//loop_id_t add_loop(LoopHandler* loop);

		void process(const uint32_t timestep_us);

		void process_request(const protocol::Request* request, protocol::Response* response);
		protocol::ResponseCode process_get_info(const protocol::Request* request, protocol::Response* response);
		protocol::ResponseCode process_comm_control(const protocol::Request* request, protocol::Response* response);
		protocol::ResponseCode process_memory_control(const protocol::Request* request, protocol::Response* response);
		protocol::ResponseCode process_user_command(const protocol::Request* request, protocol::Response* response);

		inline protocol::CommHandler* comm()
		{
			return &m_comm_handler;
		}

		inline Config* get_config() { return &m_config; }

	private:

		bool touches_forbidden_region(const protocol::MemoryBlock* block);
		bool touches_readonly_region(const protocol::MemoryBlock* block);

		//LoopHandler* m_loop_handlers[SCRUTINY_MAX_LOOP];
		Timebase m_timebase;
		protocol::CommHandler m_comm_handler;
		bool m_processing_request;
		bool m_disconnect_pending;
		Config m_config;
#if SCRUTINY_ACTUAL_PROTOCOL_VERSION == SCRUTINY_PROTOCOL_VERSION(1,0)
		protocol::CodecV1_0 m_codec;
#endif
	};
}

#endif