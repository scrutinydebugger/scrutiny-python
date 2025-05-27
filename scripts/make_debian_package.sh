#!/bin/bash
set -euo pipefail

RED='\033[0;31m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; NC='\033[0m' 
fatal() { >&2 echo -e "$RED[Fatal]$NC $1"; exit ${2:-1}; }

absnorm(){ echo $(readlink -m "$1"); }

# Find project root
NUITKA_OUTPUT=${1:-nuitka_build}
PROJECT_ROOT=$( absnorm "$( dirname "${BASH_SOURCE[0]}" )/.." )
SOURCE_DIR=$(absnorm "${NUITKA_OUTPUT}/scrutiny.dist")
OUTPUT_FOLDER=$(absnorm ${2:-"${SOURCE_DIR}/installer"})

cd ${PROJECT_ROOT}


# Check Folders exists
[ -d ${NUITKA_OUTPUT} ] || fatal "${NUITKA_OUTPUT} is not a folder"
[ -d ${SOURCE_DIR} ] || fatal "${SOURCE_DIR} is not a folder"

SCRUTINY_VERSION=$( ${SOURCE_DIR}/scrutiny.bin version --format short )

# Check version ok
[[ "$SCRUTINY_VERSION" =~ ^[0-9]\.[0-9]\.[0-9]$ ]] || fatal "SCRUTINY_VERSION is not valid: ${SCRUTINY_VERSION}"

ARCH=$(dpkg-architecture -qDEB_BUILD_ARCH)
TEMP_FOLDER=$(mktemp -d)
PKG_NAME="scrutinydebugger_${SCRUTINY_VERSION}_$ARCH"

PKG_FOLDER="${TEMP_FOLDER}/${PKG_NAME}"
echo "Creating debian package ${PKG_NAME}"
echo "Work folder: ${PKG_FOLDER}"

mkdir -p ${PKG_FOLDER}
mkdir -p ${PKG_FOLDER}/DEBIAN ${PKG_FOLDER}/opt ${PKG_FOLDER}/bin ${PKG_FOLDER}/usr/share/applications

cp ${PROJECT_ROOT}/deploy/debian/control ${PKG_FOLDER}/DEBIAN/control
sed -i "s/<VERSION>/${SCRUTINY_VERSION}/g"  ${PKG_FOLDER}/DEBIAN/control
sed -i "s/<ARCH>/$ARCH/g"  ${PKG_FOLDER}/DEBIAN/control

cp -r ${SOURCE_DIR} ${PKG_FOLDER}/opt/scrutinydebugger
cp  ${PROJECT_ROOT}/deploy/debian/scrutiny.gui.default.desktop ${PKG_FOLDER}/usr/share/applications/
cp  ${PROJECT_ROOT}/deploy/debian/scrutiny.gui.local-server.desktop ${PKG_FOLDER}/usr/share/applications/

ln -s /opt/scrutinydebugger/scrutiny.bin ${PKG_FOLDER}/bin/scrutiny
dpkg-deb --root-owner-group --build "${PKG_FOLDER}"

mkdir -p ${OUTPUT_FOLDER}
cp ${TEMP_FOLDER}/${PKG_NAME}.deb ${OUTPUT_FOLDER}

echo "[Done] File ${OUTPUT_FOLDER}/${PKG_NAME}.deb as been created!" 

rm -rf ${TEMP_FOLDER}
