// main.cpp

#ifdef ENABLE_HIL_TESTING    
static volatile bool run_app = false; // Scrutiny will write that.
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

    while(true)
    {
        read_ios(&inputs_outputs);
        if (run_app)    // Wait for scrutiny to set this to true when ENABLE_HIL_TESTING is defined
        {
            power_supply.process();
            app.process(&power_supply);
        }
        update_scrutiny();  // Refer to "Instrumenting a software" guide
    }

    return 0;
}
