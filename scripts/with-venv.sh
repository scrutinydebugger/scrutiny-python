#!/bin/bash
set -euo pipefail

VENV_ROOT=$1

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. >/dev/null 2>&1 && pwd -P )"
source "$PROJECT_ROOT/scripts/activate-venv.sh" $VENV_ROOT

exec "${@:2}"
