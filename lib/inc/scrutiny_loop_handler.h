#ifndef ___SCRUTINY_LOOP_HANDLER_H___
#define ___SCRUTINY_LOOP_HANDLER_H___

#include <cstdint>

namespace scrutiny
{
	enum LoopType
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

		void rx_bytes(uint8_t* data, uint32_t len);

	protected:
		LoopType m_loop_type;
		float m_frequency;
	};
}


#endif //___SCRUTINY_LOOP_HANDLER_H___