#!/bin/bash
set -euxo pipefail

SCRUTINY_COVERAGE_SUFFIX="${SCRUTINY_COVERAGE_SUFFIX:-dev}"
COV_DATAFILE=".coverage${SCRUTINY_COVERAGE_SUFFIX}"

python3 -m coverage run --data-file ${COV_DATAFILE} -m scrutiny runtest
python3 -m mypy scrutiny
python3 -m coverage report
