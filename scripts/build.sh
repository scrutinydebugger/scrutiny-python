#!/bin/bash
set -euo pipefail

PROJECT_ROOT=$( realpath "$( dirname "${BASH_SOURCE[0]}" )/.." )
cd ${PROJECT_ROOT}

DEPLOY_FOLDER=${PROJECT_ROOT}/deploy
ICON_PNG="${DEPLOY_FOLDER}/scrutiny-icon.png"

EXTRA_FILES=
EXTRA_FILES+=" --include-data-files=${DEPLOY_FOLDER}/windows/scrutiny.ico=scrutiny.ico"

python -m nuitka                                    \
    --follow-imports                                \
    --python-flag=no_asserts                        \
    --python-flag=no_docstrings                     \
    --python-flag=no_site                           \
    --report=nuitka_build/build_report.xml          \
    --output-dir=nuitka_build                       \
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
    --product-version="$(python -m scrutiny version --format short)" \
    --copyright="$(python -m scrutiny version)"     \
    --main=scrutiny                                 \

    
