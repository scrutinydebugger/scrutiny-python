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
