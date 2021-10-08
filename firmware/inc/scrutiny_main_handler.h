#ifndef __SCRUTINY_HANDLER_H__
#define __SCRUTINY_HANDLER_H__

#include <cstdint>

#include "scrutiny_setup.h"
#include "scrutiny_loop_handler.h"
#include "scrutiny_timebase.h"
#include "scrutiny_protocol.h"
#include "scrutiny_config.h"

namespace scrutiny
{
	class MainHandler
	{

	public:
		void init(Config* config);
		//void process_loop(loop_id_t loop);
		//loop_id_t add_loop(LoopHandler* loop);

		void process(uint32_t timestep_us);

		void process_request(Protocol::Request* request, Protocol::Response* response);
		Protocol::ResponseCode process_get_info(Protocol::Request* request, Protocol::Response* response);
		Protocol::ResponseCode process_comm_control(Protocol::Request* request, Protocol::Response* response);
		Protocol::ResponseCode process_memory_control(Protocol::Request* request, Protocol::Response* response);



		inline Protocol::CommHandler* comm()
		{
			return &m_comm_handler;
		}

		inline Config* get_config() { return &m_config; }

	private:
		//LoopHandler* m_loop_handlers[SCRUTINY_MAX_LOOP];
		Timebase m_timebase;
		Protocol::CommHandler m_comm_handler;
		bool m_processing_request;
		bool m_disconnect_pending;
		Config m_config;
#if ACTUAL_PROTOCOL_VERSION == PROTOCOL_VERSION(1,0)
		Protocol::CodecV1_0 m_codec;
#endif
	};
}

#endif