#pragma pack(push,1)

void file2func1();
void file2func1(int x);
void file2SetValues();


class classAFile2
{
public:
	int intInClassA;
};

namespace namespaceAFile2
{

	class classBFile2
	{
		class ClassBAFile2
		{
			public:
				int intInClassBA;
				classAFile2 classAInstance;
		};


		public:
			int intInClassB;
			ClassBAFile2 nestedClassInstance;
	};
}

