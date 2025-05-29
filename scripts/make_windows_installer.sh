#!/bin/bash
set -euo pipefail
source $(dirname ${BASH_SOURCE[0]})/common.sh

# Find project root
NUITKA_OUTPUT=$(dir_with_default ${1:-""} "nuitka_build")
PROJECT_ROOT="$(get_project_root)"
SOURCE_DIR="${NUITKA_OUTPUT}/scrutiny.dist"
OUTPUT_FOLDER=$(dir_with_default ${2:-""} "${NUITKA_OUTPUT}/installer")

cd ${PROJECT_ROOT}

# Check Folders exists
info "Source directory: $SOURCE_DIR"

assert_dir "$SOURCE_DIR"

SCRUTINY_VERSION=$( ${SOURCE_DIR}/scrutiny.exe version --format short )

info "Scrutiny version: $SCRUTINY_VERSION"
assert_scrutiny_version_format "$SCRUTINY_VERSION"
PKG_NAME="scrutinydebugger_v${SCRUTINY_VERSION}_setup"

cp ${PROJECT_ROOT}/deploy/windows/scrutiny.ico ${SOURCE_DIR}/

mkdir -p ${OUTPUT_FOLDER}
iscc ${PROJECT_ROOT}/deploy/windows/main.iss    \
    -DSOURCE_DIR="${SOURCE_DIR}"                \
    -DVERSION="${SCRUTINY_VERSION}"             \
    "-O${OUTPUT_FOLDER}"                        \
    "-F${PKG_NAME}"  

OUTFILE="${OUTPUT_FOLDER}/$PKG_NAME.exe"
assert_file ${OUTFILE}

success "File ${OUTFILE} has been created!"
