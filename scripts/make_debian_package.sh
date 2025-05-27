#!/bin/bash
set -euo pipefail
source $(dirname ${BASH_SOURCE[0]})/common.sh

# Find project root
NUITKA_OUTPUT=$(dir_with_default ${1:-""} "nuitka_build")
PROJECT_ROOT="$(get_project_root)"
SOURCE_DIR="${NUITKA_OUTPUT}/scrutiny.dist"
OUTPUT_FOLDER=$(dir_with_default ${2:-""} "${SOURCE_DIR}/installer")

cd ${PROJECT_ROOT}

# Check Folders exists
info "Source directory: $SOURCE_DIR"
info "Otuput directory: $OUTPUT_FOLDER"

assert_dir "$SOURCE_DIR"
assert_dir "$OUTPUT_FOLDER"

SCRUTINY_VERSION=$( ${SOURCE_DIR}/scrutiny.bin version --format short )
info "Scrutiny version: $SCRUTINY_VERSION"

assert_scrutiny_version_format "$SCRUTINY_VERSION"

ARCH="$(dpkg-architecture -qDEB_BUILD_ARCH)"
TEMP_FOLDER="$(mktemp -d)"
PKG_NAME="scrutinydebugger_${SCRUTINY_VERSION}_$ARCH"

PKG_FOLDER="${TEMP_FOLDER}/${PKG_NAME}"
info "Creating debian package: ${PKG_NAME}"
info "Work folder: ${PKG_FOLDER}"

mkdir -p "${PKG_FOLDER}"
mkdir -p "${PKG_FOLDER}/DEBIAN" "${PKG_FOLDER}/opt" "${PKG_FOLDER}/bin" "${PKG_FOLDER}/usr/share/applications"

cp "${PROJECT_ROOT}/deploy/debian/control" "${PKG_FOLDER}/DEBIAN/control"
sed -i "s/<VERSION>/${SCRUTINY_VERSION}/g"  "${PKG_FOLDER}/DEBIAN/control"
sed -i "s/<ARCH>/$ARCH/g"  ${PKG_FOLDER}/DEBIAN/control

cp -r "${SOURCE_DIR}" "${PKG_FOLDER}/opt/scrutinydebugger"
cp  "${PROJECT_ROOT}/deploy/debian/scrutiny.gui.default.desktop" "${PKG_FOLDER}/usr/share/applications/"
cp  "${PROJECT_ROOT}/deploy/debian/scrutiny.gui.local-server.desktop" "${PKG_FOLDER}/usr/share/applications/"

ln -s /opt/scrutinydebugger/scrutiny.bin ${PKG_FOLDER}/bin/scrutiny
dpkg-deb --root-owner-group --build "${PKG_FOLDER}"

mkdir -p ${OUTPUT_FOLDER}
cp ${TEMP_FOLDER}/${PKG_NAME}.deb ${OUTPUT_FOLDER}

success "File ${OUTPUT_FOLDER}/${PKG_NAME}.deb as been created!" 

rm -rf "${TEMP_FOLDER}"
