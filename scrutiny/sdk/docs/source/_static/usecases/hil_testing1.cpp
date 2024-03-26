
// ----------------
// App.h
#include <cstdint>

enum class PowerUpState{
    INIT,
    PSU_ENABLE,
    SUBMODULE1_ENABLE,
    DONE_OK,
    FAILED
};

struct InputsOutputs{
    struct{
        bool psu_ready;
        bool submodule1_ready;
        float psu_voltage_line1;
        float psu_voltage_line2;
    } in;
    struct {
        bool enable_psu;
        bool enable_submodule1;
    } out;
};


void init();
void run_application();
uint32_t timestamp_ms();
void fatal_error();
void read_ios(InputsOutputs*);


#ifdef ENABLE_HIL_TESTING
    #pragma message "HIL Testing is ENABLED"
    #define HIL_HOOK static volatile
#else
    #define HIL_HOOK 
#endif

// ----------------
// App.cpp

#define VOLTAGE_THRESHOLD_5V 4.75
#define VOLTAGE_THRESHOLD_12V 11.5
#define POWERUP_TIMEOUT_MS 500

extern InputsOutputs inputs_outputs;

/**
Runs a finite state machine that does a power up sequence based on GPIOs
*/
bool do_powerup()
{
#ifdef ENABLE_HIL_TESTING    
    static volatile bool hil_enable=false;
    static volatile bool start_powerup=false;
#endif

    HIL_HOOK PowerUpState last_state;
    HIL_HOOK PowerUpState actual_state;
    HIL_HOOK PowerUpState next_state;
    HIL_HOOK bool completed;

    last_state = PowerUpState::INIT;
    actual_state = PowerUpState::INIT;
    next_state = PowerUpState::INIT;
    completed = false;
    
    uint32_t time_entry;
    
    while(!completed)
    {
        bool state_entry = (last_state != actual_state);
        read_ios(&inputs_outputs);
        switch (actual_state){
            case PowerUpState::INIT:
            {
                 time_entry = timestamp_ms();
#ifdef ENABLE_HIL_TESTING
                if (hil_enable){
                    if (start_powerup){
                        next_state = PowerUpState::PSU_ENABLE;
                    }
                }
                else
#endif
                {
                    next_state = PowerUpState::PSU_ENABLE;
                }
                break;
            }
            case PowerUpState::PSU_ENABLE:
            {
                if (state_entry){
                    inputs_outputs.out.enable_psu=true;
                }
                if (inputs_outputs.in.psu_ready){
                    next_state = PowerUpState::SUBMODULE1_ENABLE;
                }
                break;
            }
            case PowerUpState::SUBMODULE1_ENABLE:
            {
                if (state_entry){
                    inputs_outputs.out.enable_submodule1=true;
                }
                if (inputs_outputs.in.submodule1_ready){
                    next_state = PowerUpState::DONE_OK;
                }
                break;
            }
            case PowerUpState::DONE_OK:
            {
                completed = true;
                break;
            }
            case PowerUpState::FAILED:
            {
                completed = true;
                break;
            }
        }

        if (timestamp_ms() - time_entry > POWERUP_TIMEOUT_MS){
            next_state = PowerUpState::FAILED;
        }

        last_state = actual_state;
        actual_state = next_state;
    }

    return actual_state == PowerUpState::DONE_OK;
}

int main(){
    init();
    bool powerup_ok = do_powerup();
    
    if (powerup_ok){
        run_application();
    } else {
        fatal_error();
    }

    return 0;
}