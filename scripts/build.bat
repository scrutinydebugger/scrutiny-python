if not exist build mkdir build
cmake -S . -B build
cmake --build build -j 4  || goto ERROR
@goto END

:ERROR
@echo Cannot build
@EXIT /B 1

:END
@EXIT /B 0
