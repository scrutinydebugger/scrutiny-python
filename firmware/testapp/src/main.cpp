
#include "file1.h"
#include "file2.h"

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

extern int file2GlobalInt;
extern StructD file1StructDInstance;

extern char file1GlobalChar;
extern int file1GlobalInt;
extern short file1GlobalShort;
extern long file1GlobalLong;
extern unsigned char file1GlobalUnsignedChar;
extern unsigned int file1GlobalUnsignedInt;
extern unsigned short file1GlobalUnsignedShort;
extern unsigned long file1GlobalUnsignedLong;
extern float file1GlobalFloat;
extern double file1GlobalDouble;
extern bool file1GlobalBool;

extern char file2GlobalChar;
extern int file2GlobalInt;
extern short file2GlobalShort;
extern long file2GlobalLong;
extern unsigned char file2GlobalUnsignedChar;
extern unsigned int file2GlobalUnsignedInt;
extern unsigned short file2GlobalUnsignedShort;
extern unsigned long file2GlobalUnsignedLong;
extern float file2GlobalFloat;
extern double file2GlobalDouble;
extern bool file2GlobalBool;


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


void set_global_values()
{
    file1GlobalChar = -10;
    file1GlobalInt = -1000;
    file1GlobalShort = -999;
    file1GlobalLong = -100000;
    file1GlobalUnsignedChar = 55;
    file1GlobalUnsignedInt = 100001; 
    file1GlobalUnsignedShort = 50000;
    file1GlobalUnsignedLong = 100002;
    file1GlobalFloat = 3.1415926;
    file1GlobalDouble = 1.71;
    file1GlobalBool = true;

    file2GlobalChar = 20;
    file2GlobalInt =  2000;
    file2GlobalShort =  998;
    file2GlobalLong =  555555;
    file2GlobalUnsignedChar =  254;
    file2GlobalUnsignedInt =  123456;
    file2GlobalUnsignedShort =  12345;
    file2GlobalUnsignedLong =  1234567;
    file2GlobalFloat =  0.1;
    file2GlobalDouble =  0.11111111111111;
    file2GlobalBool =  false;
}

int main(int argc, char* argv[]) 
{
    int errorcode = 0;
    static int staticIntInMainFunc = 22222;

    set_global_values();
    funcInFile1(1,2);
    file2func1();

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
