// main.cpp

void init();
void run_application();
void update_scrutiny();

EEPROMDriver eeprom_driver;
#ifdef ENABLE_EOL_CONFIGURATOR
EEPROMConfigurator eeprom_configurator(&eeprom_driver);
#endif

int main()
{
    init();
    while(true)
    {
#ifdef ENABLE_EOL_CONFIGURATOR
        eeprom_configurator.process();
#endif
        run_application();
        update_scrutiny();
    }
}
