#!/bin/bash
set -euo pipefail
DOC_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." >/dev/null 2>&1 && pwd -P )"
USECASE_ROOT="$DOC_ROOT/source/_static/usecases"
set -x

cd $USECASE_ROOT
g++ -c hil_testing1.cpp 2> /dev/null
g++ -c hil_testing1.cpp -DENABLE_HIL_TESTING 2> /dev/null