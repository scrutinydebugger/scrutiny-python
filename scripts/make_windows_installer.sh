#!/bin/bash
set -euo pipefail
source $(dirname ${BASH_SOURCE[0]})/common.sh

# Find project root
NUITKA_OUTPUT=$(dir_with_default ${1:-""} "nuitka_build")
PROJECT_ROOT="$(get_project_root)"
SOURCE_DIR="${NUITKA_OUTPUT}/scrutiny.dist"
cd ${PROJECT_ROOT}

# Check Folders exists
info "Source directory: $SOURCE_DIR"

assert_dir "$SOURCE_DIR"

SCRUTINY_VERSION=$( ${SOURCE_DIR}/scrutiny.exe version --format short )

info "Scrutiny version: $SCRUTINY_VERSION"
assert_scrutiny_version_format "$SCRUTINY_VERSION"

cp ${PROJECT_ROOT}/deploy/windows/scrutiny.ico ${SOURCE_DIR}/

iscc ${PROJECT_ROOT}/deploy/windows/main.iss -DSOURCE_DIR="${SOURCE_DIR}" -DVERSION="${SCRUTINY_VERSION}"
success "Installer generated"
