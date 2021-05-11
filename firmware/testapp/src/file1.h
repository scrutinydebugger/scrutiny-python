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
	} nestedStructInstance;
};

struct StructD
{
	unsigned int bitfieldA : 1;
	unsigned int bitfieldB : 9;
	unsigned int bitfieldC : 3;
	unsigned int bitfieldD;
};

int funcInFile1(int a, int b);