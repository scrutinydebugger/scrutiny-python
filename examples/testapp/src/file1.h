#ifndef ___FILE_1_H___
#define ___FILE_1_H___

#pragma pack(push,1)

struct StructA
{
	int structAMemberInt;
	unsigned int structAMemberUInt;
	float structAMemberFloat;
	double structAMemberDouble;
	bool structAMemberBool;
};

struct StructB
{
	int structBMemberInt;
	StructA structBMemberStructA;
};

struct StructC
{
	int structCMemberInt;
	struct{
		int nestedStructMemberInt;
		float nestedStructMemberFloat;
		struct {
			double nestedStructInstance2MemberDouble;
		}nestedStructInstance2;
	} nestedStructInstance;
};

struct StructD
{
	unsigned int bitfieldA : 4;
	unsigned int bitfieldB : 13;
	unsigned int bitfieldC : 8;
	unsigned int bitfieldD;
	unsigned int bitfieldE : 10;
};

int funcInFile1(int a, int b);
void file1SetValues();

#pragma pack(pop)

#endif  // ___FILE_1_H___