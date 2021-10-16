#include <iostream>
#include <thread>
#include <chrono>

// #include <scrutiny.h>

int main() {
    static volatile int somevar = 3;

    // scrutiny_init();

    while(true)
    {
        std::cout << "Hello World! var:" << somevar << std::endl;
        // scrutiny_tick();
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    return 0;
}
