
#include "file1.h"
#include "file2.h"

#include <iostream>
#include <iomanip>
#include <cstdint>

using namespace std;

void mainfunc1()
{
    static int mainfunc1Var = 7777777;
}

void mainfunc1(int x)
{
    (void)x;
    static double mainfunc1Var = 8888888.88;
}

void memdump(uint64_t startAddr, uint64_t length)
{
    uint64_t addr = startAddr;
    while (addr < startAddr + length)
    {
        uint8_t* ptr = reinterpret_cast<uint8_t*>(addr);
        cout << hex << setw(16) << setfill('0') << addr;
        uint64_t nToPrint = startAddr + length - addr;
        if (nToPrint > 16)
        {
            nToPrint = 16;
        }
        for (int i=0; i<nToPrint; i++)
        {
            cout << hex << setw(2) << setfill('0') << ptr[i];
        }
        cout << endl;
        addr += nToPrint;
    }
}


int main(int argc, char* argv[]) 
{
    int errorcode = 0;
    static int staticIntInMainFunc = 22222;

    file1SetValues();
    file2SetValues();
    funcInFile1(1,2);
    file2func1();
    file2func1(123);
    mainfunc1();
    mainfunc1(123);

    if (argc % 2 == 0)
    {
        errorcode = -1;
    }
    else
    {
        for (int i=0; i<(argc-1)/2; i++)
        {

            uint64_t startAddr = strtoll(argv[i*2+1], NULL, 10);
            uint64_t length = strtoll(argv[i*2+2], NULL, 10);

            if (startAddr > 0 && length > 0)
            {
                memdump(startAddr, length);
            }
            else
            {
                errorcode = -1;
                break;
            }
        }
    }

    return errorcode;
}
