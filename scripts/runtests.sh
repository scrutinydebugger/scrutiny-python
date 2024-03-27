#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. >/dev/null 2>&1 && pwd -P )"

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

set -x 

python3 -m coverage run --data-file ${COV_DATAFILE} -m scrutiny runtest
python3 -m mypy scrutiny --strict --untyped-calls-exclude=elftools
python3 -m coverage report --data-file ${COV_DATAFILE}
python3 -m coverage html --data-file ${COV_DATAFILE} -d $HTML_COVDIR
