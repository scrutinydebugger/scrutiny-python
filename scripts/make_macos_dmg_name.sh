#!/bin/bash

set -euo pipefail
source $(dirname ${BASH_SOURCE[0]})/common.sh

NUITKA_OUTPUT=$(dir_with_default ${1:-""} "nuitka_build")
PROJECT_ROOT="$(get_project_root)"
APP_DIR="${NUITKA_OUTPUT}/scrutiny.app"

SCRUTINY_EXE="${APP_DIR}/Contents/MacOS/bin/scrutiny"
SCRUTINY_VERSION=$( "$SCRUTINY_EXE" version --format short )
assert_scrutiny_version_format "$SCRUTINY_VERSION"

PKG_NAME="scrutinydebugger_v${SCRUTINY_VERSION}_$(uname -m)"
