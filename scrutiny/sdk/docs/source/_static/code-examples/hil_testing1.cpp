/*
This example is a dummy project that shows a fictive embedded application that does a power up sequence
of a fictive power supply using a Finite State Machine. The purpose of this example is to show how we can use Scrutiny 
to do Hardware In The Loop testing by controlling the flow of the application, reading/writing hardware IOs and reading 
internal states.

The file is presented as a single-file project that aggregates many files. Each file is not complete on purpose. They only show
the code relevant to this example.
*/

// --------------
// time.hpp
#include <cstdint>
uint32_t timestamp_ms();        // Reads an absolute monotonic timestamp.

// ----------------
// hardware.hpp
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

void read_ios(InputsOutputs*);  // Reads all inputs from the hardware


//------------
// power_supply.hpp
// Fictive class that handles a fictive power supply.
// We are interested in the power up sequence

#define VOLTAGE_THRESHOLD_5V 4.75
#define VOLTAGE_THRESHOLD_12V 11.5
#define POWERUP_TIMEOUT_MS 500

class PowerSupply
{
public:
    enum class PowerUpSequenceState{
        DONE_OK=0,
        INIT,
        PSU_ENABLE,
        SUBMODULE1_ENABLE,
        FAILED
    };

    void init(InputsOutputs *inputs_outputs);
    void process();
    inline bool is_success() const {
        return m_actual_state == PowerUpSequenceState::DONE_OK;
    }
    inline bool is_error() const {
        return m_actual_state == PowerUpSequenceState::FAILED;
    }
private:
    PowerUpSequenceState m_last_state;
    PowerUpSequenceState m_actual_state;
    uint32_t m_start_timestamp;
    InputsOutputs *m_ios;
};


// ----------------
// power_supply.cpp

void PowerSupply::init(InputsOutputs *inputs_outputs)
{
    m_last_state = PowerUpSequenceState::INIT;
    m_actual_state = PowerUpSequenceState::INIT;
    m_ios=inputs_outputs;
}

void PowerSupply::process()
{
    bool const state_entry = (m_last_state != m_actual_state);
    PowerUpSequenceState next_state = m_actual_state;
    switch (m_actual_state){
        case PowerUpSequenceState::INIT:
        {
            m_start_timestamp = timestamp_ms();
            next_state = PowerUpSequenceState::PSU_ENABLE;
            break;
        }
        case PowerUpSequenceState::PSU_ENABLE:
        {
            if (state_entry){
                m_ios->out.enable_psu=true;
            }
            if (m_ios->in.psu_ready){
                next_state = PowerUpSequenceState::SUBMODULE1_ENABLE;
            }
            break;
        }
        case PowerUpSequenceState::SUBMODULE1_ENABLE:
        {
            if (state_entry){
                m_ios->out.enable_submodule1=true;
            }
            if (m_ios->in.submodule1_ready){
                next_state = PowerUpSequenceState::DONE_OK;
            }
            break;
        }
        case PowerUpSequenceState::DONE_OK:
        {
            break;  // Do something here.
        }
        case PowerUpSequenceState::FAILED:
        {            
            break;  // Nothing to do, wait for a reset maybe?
        }
    }

    if (timestamp_ms() - m_start_timestamp > POWERUP_TIMEOUT_MS){
        next_state = PowerUpSequenceState::FAILED;
    }

    m_last_state = m_actual_state;
    m_actual_state = next_state;
}

//-----------------
// application.hpp
// Fictive application.
class Application{
public:
    void init();
    void process(PowerSupply* const);
};

void update_scrutiny();     // Update the scrutiny module. Not part of this example


//-----------------
// main.cpp

#ifdef ENABLE_HIL_TESTING    
static volatile bool run_app = false; // Wait for scrutiny to set it to true
#else
constexpr bool run_app = true;
#endif

InputsOutputs inputs_outputs;
PowerSupply power_supply;
Application app;

int main()
{
    app.init();  
    power_supply.init(&inputs_outputs);

    while(run_app)
    {
        read_ios(&inputs_outputs);
        power_supply.process();
        app.process(&power_supply);
        update_scrutiny();
    }

    return 0;
}