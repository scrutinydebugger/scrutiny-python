#ifndef ___SCRUTINY_TYPES_H___
#define ___SCRUTINY_TYPES_H___

typedef void (*user_command_callback_t)(uint8_t subfunction, uint8_t* request_data, uint16_t request_data_length, uint8_t* response_data, uint16_t* response_data_length, uint16_t response_max_data_length);

#endif   //  ___SCRUTINY_TYPES_H___