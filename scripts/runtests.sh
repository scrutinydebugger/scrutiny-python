#!/bin/bash
set -euxo pipefail

COVDIR="${1:-htmlcov}"

python3 -m coverage run -m scrutiny runtest
python3 -m mypy scrutiny
python3 -m coverage report
python3 -m coverage html -d $COVDIR
