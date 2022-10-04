#!/bin/bash
set -exo pipefail

python3 -m scrutiny runtest || exit 1
python3 -m mypy scrutiny || exit 1
