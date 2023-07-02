#!/bin/bash
set -euxo pipefail

python3 -m scrutiny runtest
python3 -m mypy scrutiny
