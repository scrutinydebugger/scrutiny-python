#!/bin/bash

set -euo pipefail
source $(dirname ${BASH_SOURCE[0]})/common.sh

# Find project root
NUITKA_OUTPUT=$(dir_with_default ${1:-""} "nuitka_build")
PROJECT_ROOT="$(get_project_root)"
SOURCE_DIR="${NUITKA_OUTPUT}/scrutiny.dist"

cd ${PROJECT_ROOT}

assert_dir "$SOURCE_DIR"

SCRUTINY_VERSION=$( ${SOURCE_DIR}/scrutiny.exe version --format short )

assert_scrutiny_version_format "$SCRUTINY_VERSION"
PKG_NAME="scrutinydebugger_v${SCRUTINY_VERSION}_$(uname -m)_setup"
echo ${PKG_NAME}
