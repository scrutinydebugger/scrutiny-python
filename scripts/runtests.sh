#!/bin/bash
set -euo pipefail


if [ $# -eq 0 ]; then
    echo "Python version must be specified"
    exit 1
fi

REQUIRED_VERSION="$1"

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. >/dev/null 2>&1 && pwd -P )"
${PROJECT_ROOT}/scripts/check-python-version.sh ${REQUIRED_VERSION}  || exit 1
python3 -m scrutiny runtest || exit 1