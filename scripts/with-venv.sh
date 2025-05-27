#!/bin/bash

set -euo pipefail
source $(dirname ${BASH_SOURCE[0]})/common.sh
PROJECT_ROOT="$(get_project_root)"

source "$PROJECT_ROOT/scripts/activate-venv.sh"

set -e  # activate-venv  sets +e
exec "$@"
