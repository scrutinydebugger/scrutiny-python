#!/bin/bash
set -euo pipefail

RED='\033[0;31m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; NC='\033[0m' 
fatal() { >&2 echo -e "$RED[Fatal]$NC $1"; exit ${2:-1}; }
absnorm(){ echo $(readlink -m "$1"); }

# Find project root
NUITKA_OUTPUT=${1:-nuitka_build}
PROJECT_ROOT=$( absnorm "$( dirname "${BASH_SOURCE[0]}" )/.." )
SOURCE_DIR=$(absnorm "${NUITKA_OUTPUT}/scrutiny.dist")
cd ${PROJECT_ROOT}


# Check Folders exists
[ -d ${NUITKA_OUTPUT} ] || fatal "${NUITKA_OUTPUT} is not a folder"
[ -d ${SOURCE_DIR} ] || fatal "${SOURCE_DIR} is not a folder"

SCRUTINY_VERSION=$( ${SOURCE_DIR}/scrutiny.exe version --format short )

# Check version ok
[[ "$SCRUTINY_VERSION" =~ ^[0-9]\.[0-9]\.[0-9]$ ]] || fatal "SCRUTINY_VERSION is not valid: ${SCRUTINY_VERSION}"

cp ${PROJECT_ROOT}/deploy/windows/scrutiny.ico ${SOURCE_DIR}/

iscc ${PROJECT_ROOT}/deploy/windows/main.iss -DSOURCE_DIR="${SOURCE_DIR}" -DVERSION="${SCRUTINY_VERSION}"
