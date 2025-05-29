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

# Get verion and validate
SCRUTINY_VERSION=$( ${SOURCE_DIR}/scrutiny.bin version --format short )
assert_scrutiny_version_format "$SCRUTINY_VERSION"
info "Scrutiny version: $SCRUTINY_VERSION"

# Prepare package
ARCH="$(dpkg-architecture -qDEB_BUILD_ARCH)"
TEMP_FOLDER="$(mktemp -d)"
PKG_NAME="scrutinydebugger_${SCRUTINY_VERSION}_$ARCH"

PKG_FOLDER="${TEMP_FOLDER}/${PKG_NAME}"
info "Creating debian package: ${PKG_NAME}"
info "Work folder: ${PKG_FOLDER}"

mkdir -p "${PKG_FOLDER}"
mkdir -p "${PKG_FOLDER}/DEBIAN" "${PKG_FOLDER}/opt" "${PKG_FOLDER}/bin" "${PKG_FOLDER}/usr/share/applications"

cp "${PROJECT_ROOT}/deploy/debian/control" "${PKG_FOLDER}/DEBIAN/control"   # Copy the template
sed -i "s/<VERSION>/${SCRUTINY_VERSION}/g"  "${PKG_FOLDER}/DEBIAN/control"  # Set the version in the control file
sed -i "s/<ARCH>/$ARCH/g"  ${PKG_FOLDER}/DEBIAN/control                     # Set the arch in the control file

cp -r "${SOURCE_DIR}" "${PKG_FOLDER}/opt/scrutinydebugger"                  # The program
cp  "${PROJECT_ROOT}/deploy/debian/scrutiny.gui.default.desktop" "${PKG_FOLDER}/usr/share/applications/"        # Desktop Icon : Scrutiny GUI
cp  "${PROJECT_ROOT}/deploy/debian/scrutiny.gui.local-server.desktop" "${PKG_FOLDER}/usr/share/applications/"   # Desktop Icon : Scrutiny GUI (Local)

ln -s "/opt/scrutinydebugger/scrutiny.bin" "${PKG_FOLDER}/bin/scrutiny"     # CLI launcher 
dpkg-deb --root-owner-group --build "${PKG_FOLDER}"                         # Pack

# Move the package in the wnated output folder
mkdir -p ${OUTPUT_FOLDER}
OUTFILE="${OUTPUT_FOLDER}/${PKG_NAME}.deb"
cp "${TEMP_FOLDER}/${PKG_NAME}.deb" "${OUTFILE}"

assert_file "${OUTFILE}"
success "File ${OUTFILE} has been created!" 

# Cleanup
rm -rf "${TEMP_FOLDER}"
