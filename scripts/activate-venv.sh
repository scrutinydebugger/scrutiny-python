#!/bin/bash
set -euo pipefail

GIVEN_VENV=$1

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. >/dev/null 2>&1 && pwd -P )"
PY_MODULE_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." >/dev/null 2>&1 && pwd -P )"

if [ -z "$GIVEN_VENV" ]; then
    VENV_ROOT="$GIVEN_VENV";
else
    VENV_ROOT="$PROJECT_ROOT/venv";
fi

log() { echo -e "\x1B[92m[OK]\x1B[39m $@"; }

[ ! -d "$VENV_ROOT" ] \
    && log "Missing venv. Creating..." \
    && python3 -m venv "$VENV_ROOT"

source "$VENV_ROOT/bin/activate"

if ! pip3 show wheel 2>&1 >/dev/null; then
    log "Installing wheel..."
    pip3 install wheel
    log "Upgrading pip..."
    pip3 install --upgrade pip
    log "Upgrading setuptools..."
    pip3 install --upgrade setuptools
fi

if ! diff "$PY_MODULE_ROOT/setup.py" "$VENV_ROOT/cache/setup.py" 2>&1 >/dev/null; then
    log "Install scrutiny inside venv"
    pip3 install -e "$PY_MODULE_ROOT"
    mkdir -p "$VENV_ROOT/cache/"
    cp "$PY_MODULE_ROOT/setup.py" "$VENV_ROOT/cache/setup.py"
fi
