if not exist build mkdir build
cmake -S . -B build || goto ERROR
cmake --build build -j 4 || goto ERROR
build\Debug\scrutiny_test.exe
@goto END

:ERROR
@echo Cannot run unit tests

:END
