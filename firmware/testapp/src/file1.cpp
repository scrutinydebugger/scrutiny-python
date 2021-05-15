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



namespace NamespaceInFile1
{
	namespace NamespaceInFile1Nested1
	{
		unsigned long file1GlobalNestedVar1;
		static unsigned long file1StaticNestedVar1;
	}	
}


int funcInFile1(int a, int b)
{
	static long staticLongInFuncFile1 = 10;


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


	return a+b;
}


StructA file1StructAInstance;
StructB file1StructBInstance;
StructC file1StructCInstance;
StructD file1StructDInstance;
static StructA file1StructAStaticInstance;
