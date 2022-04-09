
#include "file1.h"
#include "file2.h"
#include "argument_parser.h"
#include "scrutiny.h"
#include "udp_bridge.h"

#include <iostream>
#include <iomanip>
#include <cstdint>
#include <chrono>
#include <thread>
#include <algorithm>

using namespace std;

void mainfunc1()
{
    static int mainfunc1Var = 7777777;
    (void)mainfunc1Var;
}

void mainfunc1(int x)
{
    (void)x;
    static double mainfunc1Var = 8888888.88;
    (void)mainfunc1Var;
}

void memdump(uintptr_t startAddr, uint32_t length)
{
    uintptr_t addr = startAddr;
    while (addr < startAddr + length)
    {
        uint8_t* ptr = reinterpret_cast<uint8_t*>(addr);
        cout << "0x" << hex << setw(16) << setfill('0') << addr << ":\t";
        uint64_t nToPrint = startAddr + length - addr;
        if (nToPrint > 16)
        {
            nToPrint = 16;
        }
        for (unsigned int i=0; i<nToPrint; i++)
        {
            cout << hex << setw(2) << setfill('0') << static_cast<uint32_t>(ptr[i]);
        }
        cout << endl;
        addr += nToPrint;
    }
}

void init_all_values()
{
    file1SetValues();
    file2SetValues();
    funcInFile1(1, 2);
    file2func1();
    file2func1(123);
    mainfunc1();
    mainfunc1(123);
}


int main(int argc, char* argv[]) 
{
    static_assert(sizeof(char) == 1, "testapp doesn't support char bigger than 8 bits (yet)");

    int errorcode = 0;
    static int staticIntInMainFunc = 22222;
    (void)staticIntInMainFunc;
    init_all_values();
        
    scrutiny::MainHandler scrutiny_handler;
    scrutiny::Config config;
    config.max_bitrate = 100000;
    scrutiny_handler.init(&config);

    ArgumentParser parser;
    parser.parse(argc, argv);

    if (!parser.is_valid())
    {
        cerr << "Invalid usage" << endl << parser.error_message() << endl;
        errorcode = -1;
    }
    else
    {
        chrono::time_point<chrono::steady_clock> last_timestamp, now_timestamp;
        last_timestamp = chrono::steady_clock::now();
        now_timestamp = chrono::steady_clock::now();

        if (parser.command() == TestAppCommand::Memdump)
        {
            MemoryRegion region;
            while (parser.has_another_memory_region())
            {
                try
                {
                    parser.next_memory_region(&region);
                    memdump(region.start_address, region.length);
                }
                catch (std::exception const& e)
                {
                    cerr << e.what() << endl;
                    errorcode = -1;
                    break;
                }
            }
        }
        // Listen on a UDP port, reply to the address of the last sender.
        
        else if (parser.command() == TestAppCommand::UdpListen)
        {
            UdpBridge::global_init();
            uint8_t buffer[1024];
            UdpBridge udp_bridge(parser.udp_port());
            try
            {
                udp_bridge.start();
                int len_received = 0;
                while (true)
                {
                    len_received = udp_bridge.receive(buffer, sizeof(buffer)); // Non-blocking. Can return 0
                    now_timestamp = chrono::steady_clock::now();
                    uint32_t timestep = static_cast<uint32_t>(chrono::duration_cast<chrono::microseconds>(now_timestamp - last_timestamp).count());

                    if (len_received > 0)
                    {
                        cout << "in:  ("<< dec << len_received << ")\t" ;
                        for (int i=0; i<len_received; i++)
                        {
                            cout << hex << setw(2) << setfill('0') << static_cast<uint32_t>(buffer[i]);
                        }
                        cout << endl;
                    }

                    scrutiny_handler.comm()->receive_data(buffer, len_received);

                    uint32_t data_to_send = scrutiny_handler.comm()->data_to_send();
                    data_to_send = min(data_to_send, static_cast<uint32_t>(sizeof(buffer)));

                    if (data_to_send > 0)
                    {
                        scrutiny_handler.comm()->pop_data(buffer, data_to_send);
                        udp_bridge.reply(buffer, data_to_send); // Send to last sender.

                        cout << "out: (" << dec << data_to_send << ")\t" ;
                        for (unsigned int i=0; i<data_to_send; i++)
                        {
                            cout << hex << setw(2) << setfill('0') << static_cast<uint32_t>(buffer[i]);
                        }
                        cout << endl;
                    }

                    scrutiny_handler.process(timestep);
                    this_thread::sleep_for(chrono::milliseconds(10));
                    last_timestamp = now_timestamp;
                }
            }
            catch (std::exception const& e)
            {
                cerr << e.what() << endl;
            }

            udp_bridge.stop();
            UdpBridge::global_close();
        }
    }


    return errorcode;
}
