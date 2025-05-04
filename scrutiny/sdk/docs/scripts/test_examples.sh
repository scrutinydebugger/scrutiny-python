#!/bin/bash
set -eEuo pipefail
DOC_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." >/dev/null 2>&1 && pwd -P )"
EXAMPLES_ROOT="$DOC_ROOT/source/_static/code-examples"

tempdir=$(mktemp -d)
trap  "echo 'Error. Exiting' && rm -rf ${tempdir}" ERR

set -x

which python3
python3 --version
pip list
env

echo -e "\nTesting example code..."

cd $tempdir

# HIL testing
cd $EXAMPLES_ROOT/hil_testing
outfile="$tempdir/hil_testing.cpp"
cat *.cpp > $outfile
g++ -c "$outfile" -o "$tempdir/hil_testing.o"
g++ -c "$outfile" -o "$tempdir/hil_testing.o" -DENABLE_HIL_TESTING 
python3 -m mypy --cache-dir $tempdir hil_testing_1_powerup_check.py --strict

# EOL Config
cd $EXAMPLES_ROOT/eol_config
outfile="$tempdir/eol_config.cpp"
cat *.cpp > $outfile
g++ -c "$outfile" -o $tempdir/eol_config.o
g++ -c "$outfile" -o $tempdir/eol_config.o -DENABLE_EOL_CONFIGURATOR
python3 -m mypy --cache-dir $tempdir eol_config_assembly_header.py --strict
python3 -m mypy --cache-dir $tempdir eol_config_dump_eeprom.py --strict

# Calibration
cd $EXAMPLES_ROOT/calibration
outfile="$tempdir/calibration.cpp"
cat *.cpp > $outfile
g++ -c "$outfile" -o $tempdir/calibration.o
g++ -c "$outfile" -o $tempdir/calibration.o -DENABLE_TUNNING
python3 -m mypy --cache-dir $tempdir calibration_1_pi_graph.py --strict 


# Event looping
cd $EXAMPLES_ROOT/event_looping
python3 -m mypy --cache-dir $tempdir event_looping.py --strict 

rm -rf $tempdir
