#!/bin/bash

#    nuitka_build.sh
#        Compile the Scrutiny module to a binary using Nuitka.
#        On Windows and Linux, produces a folder with a binary and all dependencies.
#        On Mac OS, produces a mac .app bundle
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

set -euo pipefail
source $(dirname ${BASH_SOURCE[0]})/common.sh

# Define the base directories
OUTPUT_FOLDER=$(dir_with_default ${1:-""} "nuitka_build")
PROJECT_ROOT="$(get_project_root)"
cd ${PROJECT_ROOT}

DEPLOY_FOLDER=${PROJECT_ROOT}/deploy
assert_dir "$DEPLOY_FOLDER"

ICON_PNG="${DEPLOY_FOLDER}/scrutiny-icon.png"
assert_file "$ICON_PNG"

# Get the scrutiny version and validate
SCRUTINY_VERSION=$(python -m scrutiny version --format short)
COPYRIGHT_STRING=$(python -m scrutiny version)
assert_scrutiny_version_format "$SCRUTINY_VERSION"

info "Building scrutiny into ${OUTPUT_FOLDER}"
info "Using $(python --version)"

# Per platform specfic parameters
PRODUCT_NAME="Scrutiny Debugger"
PLATFORM=$(python -c "import sys; print(sys.platform);")
PLATFORM_ARGS=

OUTPUT_FILENAME="scrutiny.bin"  # default. we manage with symlink on unix based platform
if [ "$PLATFORM" = "win32" ]; then
    PLATFORM_ARGS+=" --windows-icon-from-ico=${ICON_PNG}"
    OUTPUT_FILENAME="scrutiny"  # we do not want scrutiny.bin.exe
elif [ "$PLATFORM" = "darwin" ]; then
    PLATFORM_ARGS+=" --macos-create-app-bundle"
    PLATFORM_ARGS+=" --include-data-file=${DEPLOY_FOLDER}/macos/launcher.sh=launcher.sh"
    PLATFORM_ARGS+=" --macos-app-icon=${ICON_PNG}"
elif [ "$PLATFORM" = "linux" ]; then
    :
fi

LICENSE_FILE="LICENSE.out"
./scripts/make_license.sh ${LICENSE_FILE}
assert_file ${LICENSE_FILE}

# Launch the compilation
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
    --include-data-file="${LICENSE_FILE}"="LICENSE" \
    --product-name="${PRODUCT_NAME}"                \
    --product-version="${SCRUTINY_VERSION}"         \
    --copyright="${COPYRIGHT_STRING}"               \
    ${PLATFORM_ARGS}                                \
    --output-filename=${OUTPUT_FILENAME}            \
    --main=scrutiny                                 \

if [ "$PLATFORM" = "darwin" ]; then
    # Post process stage specific to mac OS. 
    # Define some app properties + setup a symlink for CLI.
    APP_DIR="${OUTPUT_FOLDER}/scrutiny.app"
    PLIST="${APP_DIR}/Contents/Info.plist"
    # Let's replace the entry point with our launcher that adds the command line argument
    plutil -replace CFBundleExecutable          -string "launcher.sh"       "${PLIST}"  # What to launch when the user click
    plutil -replace CFBundleDisplayName         -string "Scrutiny GUI"      "${PLIST}"  # Name to display in the info
    plutil -replace CFBundleShortVersionString  -string "$SCRUTINY_VERSION" "${PLIST}"  # Version of the application to display in the info
    plutil -replace CFBundleName                -string "Scrutiny"          "${PLIST}"  # A fallback shortname if the display name is not set (it is)
    plutil -replace CFBundleIdentifier          -string "scrutiny"          "${PLIST}"  # A unique id for the application for code signature. We don't sign (for now)
    BIN_FOLDER="${APP_DIR}/Contents/MacOS/bin"
    mkdir "$BIN_FOLDER" # For the user to put in their path.
    ln -s ../${OUTPUT_FILENAME} $BIN_FOLDER/scrutiny
fi

success "Nuitka compilation completed"
