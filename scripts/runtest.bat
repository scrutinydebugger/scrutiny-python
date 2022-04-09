@cmd /c scripts\build.bat || goto ERROR
build\lib\test\Debug\scrutiny_unittest.exe
@goto END

:ERROR
@echo Cannot run unit tests

:END
