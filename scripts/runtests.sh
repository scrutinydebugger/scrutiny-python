#!/bin/bash
set -euo pipefail
set -x

python3 -m scrutiny runtest || exit 1
python3 -m mypy scrutiny || exit 1