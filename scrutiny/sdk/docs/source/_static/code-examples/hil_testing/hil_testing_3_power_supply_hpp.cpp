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
