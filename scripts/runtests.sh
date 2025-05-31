#!/bin/bash

#    runtests.sh
#        Run all scrutiny tests. To be run by CI
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2021 Scrutiny Debugger

set -euo pipefail
source $(dirname ${BASH_SOURCE[0]})/common.sh
PROJECT_ROOT="$(get_project_root)"

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
export QT_QPA_PLATFORM=offscreen
python3 -m mypy scrutiny  # .mypy.ini dictacte the rules
python3 -m coverage run --data-file ${COV_DATAFILE} -m scrutiny runtest
python3 -m coverage report --data-file ${COV_DATAFILE}
python3 -m coverage html --data-file ${COV_DATAFILE} -d $HTML_COVDIR
