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
