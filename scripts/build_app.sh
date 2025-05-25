#!/bin/bash
set -euo pipefail

PROJECT_ROOT=$( realpath "$( dirname "${BASH_SOURCE[0]}" )/.." )
cd ${PROJECT_ROOT}

DEPLOY_FOLDER=${PROJECT_ROOT}/deploy
ICON_PNG="${DEPLOY_FOLDER}/scrutiny-icon.png"

EXTRA_FILES=
EXTRA_FILES+=" --include-data-files=${DEPLOY_FOLDER}/windows/scrutiny.ico=scrutiny.ico"

SCRUTINY_VERSION=$(python -m scrutiny version --format short)
COPYRIGHT_STRING=$(python -m scrutiny version)
OUTPUT_FOLDER='nuitka_build'

python -m nuitka                                    \
    --follow-imports                                \
    --python-flag=no_docstrings                     \
    --python-flag=no_site                           \
    --output-dir=${OUTPUT_FOLDER}                   \
    --standalone                                    \
    --nofollow-import-to=ipdb                       \
    --nofollow-import-to=test                       \
    --enable-plugin=pyside6                         \
    --assume-yes-for-downloads                      \
    --noinclude-unittest-mode=allow                 \
    --windows-icon-from-ico=${ICON_PNG}             \
    --macos-app-icon=${ICON_PNG}                    \
    --include-package-data=scrutiny.gui.assets      \
    ${EXTRA_FILES}                                  \
    --product-name="Scrutiny Debugger"              \
    --product-version="${SCRUTINY_VERSION}"         \
    --copyright="${COPYRIGHT_STRING}"               \
    --main=scrutiny                                 \

${PROJECT_ROOT}/scripts/make_windows_installer.bat "${SCRUTINY_VERSION}" "${OUTPUT_FOLDER}/scrutiny.dist"
