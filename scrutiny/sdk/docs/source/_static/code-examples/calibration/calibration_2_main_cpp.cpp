// main.cpp

constexpr float CONTROL_LOOP_FREQ = 10000.0f;
constexpr float CONTROLLER_KP = 2.0;
constexpr float CONTROLLER_KI = 0.1;
constexpr float CONTROLLER_MIN = 0;
constexpr float CONTROLLER_MAX = 1;
constexpr float CONTROLLER_MARGIN = 0.02;


PIControllerSat m_controller(1.0f/CONTROL_LOOP_FREQ, CONTROLLER_KP, CONTROLLER_KI, CONTROLLER_MIN, CONTROLLER_MAX, CONTROLLER_MARGIN);

float read_feedback();          // Reads the controller feedback (from an IO port)
float get_setpoint();           // Get the setpoint from another module of the software (user input, antoher algorithm)
void apply_comand(float cmd);   // Apply the command computed by the controller to an output

void start_scheduler_task(void(*func)() , float freq);
void idle_task();
void init_scrutiny();
void scrutiny_run_10khz_loop_handler(); 

void control_task_10khz()
{
    float setpoint;
#ifdef ENABLE_TUNNING
    static volatile bool manual_control = false;
    static volatile float manual_control_setpoint = 0.0f;
    
    if (manual_control)
    {
        setpoint=manual_control_setpoint;
    }
    else
#endif    
    {
        setpoint = get_setpoint();
    }

    m_controller.set_inputs(read_feedback(), setpoint);
    m_controller.update();
    apply_comand(m_controller.out());

    // Scrutiny loop handler would be run here. Enables Datalogging
    scrutiny_run_10khz_loop_handler();  
}

int main(){
    init_scrutiny(); // Configuration of datalogging and registration of the 10khz loop would happen here
    start_scheduler_task(control_task_10khz, CONTROL_LOOP_FREQ);
    while(true){
        idle_task(); // Scrutiny Main Handler would be run here
    }
}
