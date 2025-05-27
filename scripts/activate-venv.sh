#!/bin/bash
set -uo pipefail

source $(dirname ${BASH_SOURCE[0]})/common.sh
set +e

PROJECT_ROOT="$(get_project_root)"
PY_MODULE_ROOT="$PROJECT_ROOT"

SCRUTINY_VENV_DIR="${SCRUTINY_VENV_DIR:-venv}"
SCRUTINY_VENV_ROOT="${SCRUTINY_VENV_DIR:-$PROJECT_ROOT/$SCRUTINY_VENV_DIR}"

[ ! -d "$SCRUTINY_VENV_ROOT" ] \
    && info "Missing venv. Creating..." \
    && python3 -m venv "$SCRUTINY_VENV_ROOT"

source "$SCRUTINY_VENV_ROOT/bin/activate"


MODULE_FEATURE="[dev]"
if ! [[ -z "${BUILD_CONTEXT+x}" ]]; then
    if [[ "$BUILD_CONTEXT" == "ci" ]]; then
        MODULE_FEATURE="[test]" # Will cause testing tools to be installed.
        export PIP_CACHE_DIR=$SCRUTINY_VENV_ROOT/pip_cache   # Avoid concurrent cache access issue on CI
    fi
fi

pip3 cache info

if ! pip3 show wheel 2>&1 >/dev/null; then
    info "Installing wheel..."
    pip3 install wheel
    info "Upgrading pip..."
    pip3 install --upgrade pip
    info "Upgrading setuptools..."
    pip3 install --upgrade setuptools
fi

if ! diff "$PY_MODULE_ROOT/setup.py" "$SCRUTINY_VENV_ROOT/cache/setup.py" 2>&1 >/dev/null; then
    info "Install scrutiny inside venv"
    pip3 install -e "${PY_MODULE_ROOT}${MODULE_FEATURE}"
    mkdir -p "$SCRUTINY_VENV_ROOT/cache/"
    cp "$PY_MODULE_ROOT/setup.py" "$SCRUTINY_VENV_ROOT/cache/setup.py"
fi

set +e
