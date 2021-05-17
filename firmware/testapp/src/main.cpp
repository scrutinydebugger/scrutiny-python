
#include "file1.h"
#include "file2.h"

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>


void mainfunc1()
{
    static int mainfunc1Var = 7777777;
}

void mainfunc1(int x)
{
    static double mainfunc1Var = 8888888.88;
}

void memdump(unsigned long startAddr, unsigned long length)
{
    unsigned long addr = startAddr;
    while (addr < startAddr + length)
    {
        uint8_t* ptr = (uint8_t*)(addr);
        printf("0x%08X:    ", addr);
        int nToPrint = startAddr + length - addr;
        if (nToPrint > 16)
        {
            nToPrint = 16;
        }
        for (int i=0; i<nToPrint; i++)
        {
            printf("%02X", ptr[i]);
        }
        printf("\n");
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

            long startAddr = strtol(argv[i*2+1], NULL, 10);
            long length = strtol(argv[i*2+2], NULL, 10);

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
