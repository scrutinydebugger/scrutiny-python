
set(SCRUTINY_INCLUDE_DIR
	inc/
	inc/protocol/
	)

set(SCRUTINY_SOURCES 
	src/scrutiny_main_handler.cpp
	src/scrutiny_loop_handler.cpp
	src/scrutiny_crc.cpp
	src/scrutiny_software_id.cpp
	src/scrutiny_config.cpp
	src/protocol/scrutiny_comm_handler.cpp
	src/protocol/scrutiny_codec_v1_0.cpp
	src/protocol/scrutiny_protocol_definitions.cpp
	src/protocol/scrutiny_protocol_tools.cpp

	inc/scrutiny.h
	inc/scrutiny_crc.h
	inc/scrutiny_loop_handler.h
	inc/scrutiny_main_handler.h
	inc/scrutiny_setup.h
	inc/scrutiny_software_id.h
	inc/scrutiny_timebase.h
	inc/scrutiny_config.h
	inc/protocol/scrutiny_protocol.h
	inc/protocol/scrutiny_comm_handler.h
	inc/protocol/scrutiny_protocol_definitions.h
	inc/protocol/scrutiny_codec_v1_0.h
	inc/protocol/scrutiny_protocol_tools.h
	)

