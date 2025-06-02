#!/bin/bash

#    with-venv.sh
#        Run a command inside the virtual environment
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

set -euo pipefail
source $(dirname ${BASH_SOURCE[0]})/common.sh
PROJECT_ROOT="$(get_project_root)"

source "$PROJECT_ROOT/scripts/activate-venv.sh"

set -e  # activate-venv  sets +e
exec "$@"
