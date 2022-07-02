#!/bin/bash
set -euo pipefail

python3 -m scrutiny runtest || exit 1