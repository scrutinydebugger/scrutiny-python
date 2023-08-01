#!/bin/bash
set -euxo pipefail

SCRUTINY_COVERAGE_SUFFIX="${SCRUTINY_COVERAGE_SUFFIX:-dev}"

HTML_COVDIR="htmlcov_${SCRUTINY_COVERAGE_SUFFIX}"
COV_DATAFILE=".coverage_${SCRUTINY_COVERAGE_SUFFIX}"

python3 -m coverage run --data-file ${COV_DATAFILE} -m scrutiny runtest
python3 -m mypy scrutiny
python3 -m coverage report --data-file ${COV_DATAFILE}

MAKE_HTML=1
if ! [[ -z "${BUILD_CONTEXT+x}" ]]; then
    if [[ "$BUILD_CONTEXT" == "ci" ]]; then
        MAKE_HTML=0 # No HTML report on CI
    fi
fi
if [ $MAKE_HTML ]; then
    python3 -m coverage html --data-file ${COV_DATAFILE} -d $HTML_COVDIR
fi
