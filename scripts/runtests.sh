#!/bin/bash
set -uxo pipefail

SCRUTINY_COVERAGE_SUFFIX="${SCRUTINY_COVERAGE_SUFFIX:-dev}"
HTML_COVDIR="htmlcov_${SCRUTINY_COVERAGE_SUFFIX}"
COV_DATAFILE=".coverage_${SCRUTINY_COVERAGE_SUFFIX}"

if ! [[ -z "${BUILD_CONTEXT+x}" ]]; then
    if [[ "$BUILD_CONTEXT" == "ci" ]]; then
        if ! [[ -z "${NODE_NAME+x}" ]]; then
            echo "Running tests on agent: ${NODE_NAME}"
        fi
    fi
fi

set -e 

python3 -m coverage run --data-file ${COV_DATAFILE} -m scrutiny runtest --loglevel debug
python3 -m mypy scrutiny
python3 -m coverage report --data-file ${COV_DATAFILE}
python3 -m coverage html --data-file ${COV_DATAFILE} -d $HTML_COVDIR
  