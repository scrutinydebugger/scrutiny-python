
#include "file1.h"
#include "file2.h"

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

extern int file2GlobalInt;
extern StructD file1StructDInstance;

void mainfunc1()
{
    static int mainfunc1Var;
}

void mainfunc1(int x)
{
    static double mainfunc1Var;
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
    static int staticIntInMainFunc=0;
    file2GlobalInt = 123;

    file1StructDInstance.bitfieldA = 1;
    file1StructDInstance.bitfieldB = 0b100111011;
    file1StructDInstance.bitfieldC = 0b11;
    file1StructDInstance.bitfieldD = 0b101001101;

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
