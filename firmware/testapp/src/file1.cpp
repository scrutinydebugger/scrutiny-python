#include "file1.h"

char file1GlobalChar;
int file1GlobalInt;
short file1GlobalShort;
long file1GlobalLong;
unsigned char file1GlobalUnsignedChar;
unsigned int file1GlobalUnsignedInt;
unsigned short file1GlobalUnsignedShort;
unsigned long file1GlobalUnsignedLong;
float file1GlobalFloat;
double file1GlobalDouble;
bool file1GlobalBool;


static char file1StaticChar;
static int file1StaticInt;
static short file1StaticShort;
static long file1StaticLong;
static unsigned char file1StaticUnsignedChar;
static unsigned int file1StaticUnsignedInt;
static unsigned short file1StaticUnsignedShort;
static unsigned long file1StaticUnsignedLong;
static float file1StaticFloat;
static double file1StaticDouble;
static bool file1StaticBool;

static StructA file1StructAStaticInstance;

StructA file1StructAInstance;
StructB file1StructBInstance;
StructC file1StructCInstance;
StructD file1StructDInstance;

namespace NamespaceInFile1
{
	namespace NamespaceInFile1Nested1
	{
		unsigned long file1GlobalNestedVar1;
		static unsigned long file1StaticNestedVar1;
	}	
}


void file1SetValues()
{
	file1StaticChar = 99;
	file1StaticInt = 987654;
	file1StaticShort = -666;
	file1StaticLong = -55555;
	file1StaticUnsignedChar = 44;
	file1StaticUnsignedInt = 3333;
	file1StaticUnsignedShort = 22222;
	file1StaticUnsignedLong = 321321;
	file1StaticFloat = 1.23456789;
	file1StaticDouble = 9.87654321;
	file1StaticBool = true;

	file1StructAStaticInstance.structAMemberInt = -789;
	file1StructAStaticInstance.structAMemberUInt = 147258;
	file1StructAStaticInstance.structAMemberFloat = 88.88;
	file1StructAStaticInstance.structAMemberDouble = 99.99;
	file1StructAStaticInstance.structAMemberBool = true ;

	NamespaceInFile1::NamespaceInFile1Nested1::file1StaticNestedVar1 = 78945612345;

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

    file1StructAInstance.structAMemberInt = -654;
    file1StructAInstance.structAMemberUInt = 258147;
    file1StructAInstance.structAMemberFloat = 77.77;
    file1StructAInstance.structAMemberDouble = 66.66;
    file1StructAInstance.structAMemberBool = false ;

    file1StructBInstance.structBMemberInt = 55555;
    file1StructBInstance.structBMemberStructA.structAMemberInt = -199999;
    file1StructBInstance.structBMemberStructA.structAMemberUInt = 33333;
    file1StructBInstance.structBMemberStructA.structAMemberFloat = 33.33;
    file1StructBInstance.structBMemberStructA.structAMemberDouble = 22.22;
    file1StructBInstance.structBMemberStructA.structAMemberBool = true ;

    file1StructCInstance.structCMemberInt = 888874;
    file1StructCInstance.nestedStructInstance.nestedStructMemberInt = 2298744;
    file1StructCInstance.nestedStructInstance.nestedStructMemberFloat = -147.55;
    file1StructCInstance.nestedStructInstance.nestedStructInstance2.nestedStructInstance2MemberDouble = 654.654;

    file1StructDInstance.bitfieldA = 13;
    file1StructDInstance.bitfieldB = 4100;
    file1StructDInstance.bitfieldC = 222;
    file1StructDInstance.bitfieldD = 1234567;
    file1StructDInstance.bitfieldE = 777;

    NamespaceInFile1::NamespaceInFile1Nested1::file1GlobalNestedVar1 = 11111111111111;
}

int funcInFile1(int a, int b)
{
	static long staticLongInFuncFile1 = -0x123456789abcdef;
	return a+b;
}



