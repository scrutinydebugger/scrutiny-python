// pi_controller_sat.hpp
#include <algorithm>

// When tuning is enabled, tunables becomes volatile variable
// preventing optimization and ensuring  live updates works all the time.
#ifdef ENABLE_TUNNING
    #define TUNABLE_CONST volatile
    #define TUNABLE volatile
#else
    #define TUNABLE_CONST const
    #define TUNABLE
#endif

inline float saturate(float const v, float const min, float const max){
    return std::min(std::max(v, min), max);
}

// PI controller system with saturated output
class PIControllerSat{
public:   
    PIControllerSat(float const ts, 
        float TUNABLE_CONST kp, 
        float TUNABLE_CONST ki, 
        float TUNABLE_CONST min, 
        float TUNABLE_CONST max, 
        float TUNABLE_CONST sat_margin
    ):
        m_feedback{0.0f},
        m_ref{0.0f},
        m_out{0.0f},
        m_state{0.0f},
        m_kp{kp},
        m_ki{ki},
        m_min{min},
        m_max{max},
        m_sat_margin{sat_margin},
        m_ts{ts}
    {}

    void reset(float val=0.0f){
        m_out = val;
        float const err = m_ref-m_feedback;
        float const err_kp_sat = saturate(err*m_kp, m_min, m_max);
        float const err_ki_ts = err*m_ki*m_ts;
        m_state = 0.0f-err_ki_ts-err_kp_sat;
    }

    inline void set_inputs(float const feedback, float const ref){
        m_feedback=feedback;
        m_ref=ref;
    }

    void update(){
        float const err = m_ref-m_feedback;
        float const err_kp_sat = saturate(err*m_kp, m_min, m_max);
        float const err_ki_ts = err*m_ki*m_ts;
        float const pre_sat_out = saturate(err_kp_sat+err_ki_ts+m_state, m_min-m_sat_margin, m_max+m_sat_margin);
        m_out = saturate(pre_sat_out, m_min, m_max);
        m_state = pre_sat_out-err_kp_sat;
    }

    inline float out() const{
        return m_out;
    }

private:
    // volatile when tuning is enabled.  (calibration)
    float TUNABLE m_feedback;
    float TUNABLE m_ref;
    float TUNABLE m_out;
    float TUNABLE m_state;
    
    // volatile when tuning is enabled. (calibration)
    // const when tuning is disabled (production)
    float TUNABLE_CONST m_kp;
    float TUNABLE_CONST m_ki;
    float TUNABLE_CONST m_max;
    float TUNABLE_CONST m_min;
    float TUNABLE_CONST m_sat_margin;
    float const m_ts;
};
