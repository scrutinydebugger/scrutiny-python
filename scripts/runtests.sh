#!/bin/bash
set -euxo pipefail

python3 -m coverage run -m scrutiny runtest
python3 -m mypy scrutiny
python3 -m coverage report
