#!/bin/bash
set -euo pipefail
DOC_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." >/dev/null 2>&1 && pwd -P )"
EXAMPLES_ROOT="$DOC_ROOT/source/_static/code-examples"
set -x

cd $EXAMPLES_ROOT
g++ -c hil_testing1.cpp 2> /dev/null
g++ -c hil_testing1.cpp -DENABLE_HIL_TESTING 2> /dev/null