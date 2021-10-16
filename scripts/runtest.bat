if not exist build mkdir build
cmake -S . -B build || goto ERROR
cmake --build build -j 4 || goto ERROR
build\lib\test\Debug\scrutiny_unittest.exe
@goto END

:ERROR
@echo Cannot run unit tests

:END
