#!/bin/bash
set -euo pipefail
source $(dirname ${BASH_SOURCE[0]})/common.sh

OUTPUT_FOLDER=$(dir_with_default ${1:-""} "nuitka_build")
PROJECT_ROOT="$(get_project_root)"

cd ${PROJECT_ROOT}

DEPLOY_FOLDER=${PROJECT_ROOT}/deploy
assert_dir "$DEPLOY_FOLDER"

ICON_PNG="${DEPLOY_FOLDER}/scrutiny-icon.png"
assert_file "$ICON_PNG"

SCRUTINY_VERSION=$(python -m scrutiny version --format short)
COPYRIGHT_STRING=$(python -m scrutiny version)
assert_scrutiny_version_format "$SCRUTINY_VERSION"

info "Building scrutiny into ${OUTPUT_FOLDER}"

PRODUCT_NAME="Scrutiny Debugger"
PLATFORM=$(python -c "import sys; print(sys.platform);")
PLATFORM_ARGS=
if [ "$PLATFORM"="win32" ]; then
    PLATFORM_ARGS+=" --windows-icon-from-ico=${ICON_PNG}" 
elif [ "$PLATFORM"="darwin" ]; then
    PLATFORM_ARGS+=" --macos-app-icon=${ICON_PNG}"
    PLATFORM_ARGS+=" --macos-create-app-bundle"
    PLATFORM_ARGS+=" --macos-app-name="${PRODUCT_NAME}""
    PLATFORM_ARGS+=" --macos-app-version="${SCRUTINY_VERSION}""
elif [ "$PLATFORM"="linux" ]; then
    :
fi


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
    --include-package-data=scrutiny.gui.assets      \
    --product-name="${PRODUCT_NAME}"                \
    --product-version="${SCRUTINY_VERSION}"         \
    --copyright="${COPYRIGHT_STRING}"               \
    --main=scrutiny                                 \
    --output-filename=scrutiny.bin                  \
    ${PLATFORM_ARGS}                                \

success "Nuitka compilation completed"
