//    scrutiny_loop_handler.h
//        LoopHandler definition.
//        Loop Handler is to be run in a specific time domain and will make some features available
//        that depends on the execution requency such as embedded datalogging
//
//   - License : MIT - See LICENSE file.
//   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
//
//   Copyright (c) 2021-2022 scrutinydebugger

#ifndef ___SCRUTINY_LOOP_HANDLER_H___
#define ___SCRUTINY_LOOP_HANDLER_H___

#include <cstdint>

namespace scrutiny
{
	enum class LoopType
	{
		FIXED_FREQ,
		VARIABLE_FREQ
	};


	class LoopHandler
	{
	public:
		LoopHandler(LoopType type, float frequency);
		void init();
		void process();

		//void rx_bytes(uint8_t* data, uint32_t len);

	protected:
		LoopType m_loop_type;
		float m_frequency;
	};
}


#endif //___SCRUTINY_LOOP_HANDLER_H___