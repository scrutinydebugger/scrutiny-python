#!/bin/bash
set -eEuo pipefail
DOC_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." >/dev/null 2>&1 && pwd -P )"
EXAMPLES_ROOT="$DOC_ROOT/source/_static/code-examples"

tempdir=$(mktemp -d)
trap  "echo 'Error. Exiting' && rm -rf ${tempdir}" ERR

set -x

echo -e "\nTesting example code..."

cd $tempdir

# HIL testing
cd $EXAMPLES_ROOT/hil_testing
outfile="$tempdir/hil_testing.cpp"
cat *.cpp > $outfile

g++ -c "$outfile" -o "$tempdir/hil_testing.o"
g++ -c "$outfile" -o "$tempdir/hil_testing.o" -DENABLE_HIL_TESTING 
python -m mypy "$EXAMPLES_ROOT/hil_testing1.py" --strict

# EOL Config

cd $EXAMPLES_ROOT/eol_config
outfile="$tempdir/eol_config.cpp"
cat *.cpp > $outfile
g++ -c "$outfile" -o $tempdir/eol_config.o
g++ -c "$outfile" -o $tempdir/eol_config.o -DENABLE_EOL_CONFIGURATOR
python -m mypy "$EXAMPLES_ROOT/eol_config1.py" --strict
python -m mypy "$EXAMPLES_ROOT/eol_config2.py" --strict

rm -rf $tempdir
