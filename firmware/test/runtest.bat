cmake -S . -B build
@if not %ERRORLEVEL% == 0 goto ERROR
cmake --build build
@if not %ERRORLEVEL% == 0 goto ERROR
build\Debug\scrutiny_test.exe
goto END

:ERROR
@echo Cannot run unit tests

:END
