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
namespaceAFile2::classBFile2 file2ClassBInstance;
int file2GlobalArray1Int5[5];
float file2GlobalArray2x2Float[2][2];


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
static namespaceAFile2::classBFile2 file2ClassBStaticInstance;

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

NamespaceInFile2::EnumA instance2_enumA;
static NamespaceInFile2::EnumA staticInstance2_enumA;

void file2SetValues()
{
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

    file2StaticChar = -66;
    file2StaticInt = -8745;
    file2StaticShort = -9876;
    file2StaticLong = -12345678;
    file2StaticUnsignedChar = 12;
    file2StaticUnsignedInt = 34;
    file2StaticUnsignedShort = 56;
    file2StaticUnsignedLong = 78;
    file2StaticFloat = 2.22222;
    file2StaticDouble = 3.3333;
    file2StaticBool = true;

    NamespaceInFile2::instance_enumA = NamespaceInFile2::eVal2;
    NamespaceInFile2::staticInstance_enumA = NamespaceInFile2::eVal3;
    instance2_enumA = NamespaceInFile2::eVal4;
    staticInstance2_enumA = NamespaceInFile2::eVal1;
    
    file2GlobalArray1Int5[0] = 1111;
    file2GlobalArray1Int5[1] = 2222;
    file2GlobalArray1Int5[2] = 3333;
    file2GlobalArray1Int5[3] = 4444;
    file2GlobalArray1Int5[4] = 5555;

    file2GlobalArray2x2Float[0][0] = 1.1;
    file2GlobalArray2x2Float[0][1] = 2.2;
    file2GlobalArray2x2Float[1][0] = 3.3;
    file2GlobalArray2x2Float[1][1] = 4.4;

    file2ClassBInstance.intInClassB = -11111;
    file2ClassBInstance.nestedClassInstance.intInClassBA = -22222;
    file2ClassBInstance.nestedClassInstance.classAInstance.intInClassA = -33333;
    
    file2ClassBStaticInstance.intInClassB = -11111;
    file2ClassBStaticInstance.nestedClassInstance.intInClassBA = -22222;
    file2ClassBStaticInstance.nestedClassInstance.classAInstance.intInClassA = -33333;
}

void file2func1()
{
    static int file2func1Var = -88778877;
}

void file2func1(int x)
{
    static double file2func1Var = 963258741.123;
}




