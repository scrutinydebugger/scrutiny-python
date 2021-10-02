cmake -S . -B build || goto ERROR
cmake --build build || goto ERROR
build\Debug\scrutiny_test.exe
@goto END

:ERROR
@echo Cannot run unit tests

:END
