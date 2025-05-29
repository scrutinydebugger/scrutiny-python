#!/bin/bash
set -euo pipefail
source $(dirname ${BASH_SOURCE[0]})/common.sh

# Find project root
NUITKA_OUTPUT=$(dir_with_default ${1:-""} "nuitka_build")
PROJECT_ROOT="$(get_project_root)"
APP_DIR="${NUITKA_OUTPUT}/scrutiny.app"
OUTPUT_FOLDER=$(dir_with_default ${2:-""} "${NUITKA_OUTPUT}/installer")
mkdir -p "$OUTPUT_FOLDER"

cd ${PROJECT_ROOT}

# Check Folders exists
info "App directory: $APP_DIR"
info "Otuput directory: $OUTPUT_FOLDER"

assert_dir "$APP_DIR"
assert_dir "$OUTPUT_FOLDER"

# Get the executable
SCRUTINY_EXE="${APP_DIR}/Contents/MacOS/bin/scrutiny"

# Get the version
SCRUTINY_VERSION=$( "$SCRUTINY_EXE" version --format short )
assert_scrutiny_version_format "$SCRUTINY_VERSION"
info "Scrutiny version: $SCRUTINY_VERSION"

# Make the DMG
DMG_NAME="scrutinydebugger_v${SCRUTINY_VERSION}.dmg"
DMG_FILE=${OUTPUT_FOLDER}/${DMG_NAME}
TEMP_DIR=$(mktemp -d)
APP_NAME="Scrutiny GUI"
PACKAGE_DIR="${TEMP_DIR}/${APP_NAME}.app"
set -x
cp -R "${APP_DIR}" "${PACKAGE_DIR}"
hdiutil create -volname "Scrutiny Debugger v${SCRUTINY_VERSION}" -srcfolder "${PACKAGE_DIR}" -ov -format UDZO "${DMG_FILE}"

# Finish and cleanup
assert_file "$DMG_FILE"
success "File ${DMG_FILE} has been created!"

rm -rf "${TEMP_DIR}"
