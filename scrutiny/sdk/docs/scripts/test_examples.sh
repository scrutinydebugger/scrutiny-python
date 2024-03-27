#!/bin/bash
set -eEuo pipefail
DOC_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." >/dev/null 2>&1 && pwd -P )"
EXAMPLES_ROOT="$DOC_ROOT/source/_static/code-examples"

tempdir=$(mktemp -d)
trap  "echo 'Error. Exiting' && rm -rf ${tempdir}" ERR

set -x

cd $tempdir
g++ -c "$EXAMPLES_ROOT/hil_testing1.cpp"
g++ -c "$EXAMPLES_ROOT/hil_testing1.cpp" -DENABLE_HIL_TESTING

python -m mypy "$EXAMPLES_ROOT/hil_testing1.py" --strict

rm -rf $tempdir