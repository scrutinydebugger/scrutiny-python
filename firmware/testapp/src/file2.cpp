#include "file2.h"

char file2GlobalChar;
int file2GlobalInt;
short file2GlobalShort;
long file2GlobalLong;
unsigned char file2GlobalUnsignedChar;
unsigned int file2GlobalUnsignedInt;
unsigned short file2GlobalUnsignedShort;
unsigned long file2GlobalUnsignedLong;
float file2GlobalFloat;
double file2GlobalDouble;
bool file2GlobalBool;


static char file2StaticChar;
static int file2StaticInt;
static short file2StaticShort;
static long file2StaticLong;
static unsigned char file2StaticUnsignedChar;
static unsigned int file2StaticUnsignedInt;
static unsigned short file2StaticUnsignedShort;
static unsigned long file2StaticUnsignedLong;
static float file2StaticFloat;
static double file2StaticDouble;
static bool file2StaticBool;

extern int file1GlobalInt;


namespace NamespaceInFile2
{
    enum EnumA
    {
        eVal1,
        eVal2,
        eVal3 = 100,
        eVal4
    };

    EnumA instance_enumA;
    static EnumA staticInstance_enumA;
}

void file2func1()
{
    static int file2func1Var;
}

void file2func1(int x)
{
    static double file2func1Var;
}

NamespaceInFile2::EnumA instance2_enumA;
static NamespaceInFile2::EnumA staticInstance2_enumA;


