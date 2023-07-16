#!/bin/bash
set -eo pipefail

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. >/dev/null 2>&1 && pwd -P )"
PY_MODULE_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." >/dev/null 2>&1 && pwd -P )"

SCRUTINY_VENV_DIR="${SCRUTINY_VENV_DIR:-venv}"
SCRUTINY_VENV_ROOT="${SCRUTINY_VENV_DIR:-$PROJECT_ROOT/$SCRUTINY_VENV_DIR}"

log() { echo -e "\x1B[92m[OK]\x1B[39m $@"; }

[ ! -d "$SCRUTINY_VENV_ROOT" ] \
    && log "Missing venv. Creating..." \
    && python3 -m venv "$SCRUTINY_VENV_ROOT"

source "$SCRUTINY_VENV_ROOT/bin/activate"

if ! pip3 show wheel 2>&1 >/dev/null; then
    log "Installing wheel..."
    pip3 install wheel
    log "Upgrading pip..."
    pip3 install --upgrade pip
    log "Upgrading setuptools..."
    pip3 install --upgrade setuptools
fi

MODULE_FEATURE=""
if ! [[ -z "${BUILD_CONTEXT+x}" ]]; then
    if [[ "$BUILD_CONTEXT" == "ci" ]]; then
        MODULE_FEATURE="[test]" # Will cause testing tools to be installed.
    fi
fi

if ! diff "$PY_MODULE_ROOT/setup.py" "$SCRUTINY_VENV_ROOT/cache/setup.py" 2>&1 >/dev/null; then
    log "Install scrutiny inside venv"
    pip3 install -e "${PY_MODULE_ROOT}${MODULE_FEATURE}"
    mkdir -p "$SCRUTINY_VENV_ROOT/cache/"
    cp "$PY_MODULE_ROOT/setup.py" "$SCRUTINY_VENV_ROOT/cache/setup.py"
fi

set +e
