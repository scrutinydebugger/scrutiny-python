#!/bin/bash

#    make_license.sh
#        Creates the license file to be bundled with the release package
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

set -euo pipefail 
source $(dirname ${BASH_SOURCE[0]})/common.sh
PROJECT_ROOT="$(get_project_root)"
OUTFILE=${1:-"LICENSE.out"}
cd ${PROJECT_ROOT}

packages=(
    appdirs
    pyelftools
    sortedcontainers
    pyserial
    pylink-square
    PySide6-QtAds
    PySide6
)

cp LICENSE ${OUTFILE}

echo -e "\n\nThis package is bundled with its dependncies. Each of them having their own license. See below" >>  ${OUTFILE}

python ./scripts/format_package_license.py ${packages[@]} >> "${OUTFILE}"
