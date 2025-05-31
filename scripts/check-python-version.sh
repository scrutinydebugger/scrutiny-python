#!/bin/bash

#    check-python-version.sh
#        Check that the python executable is running the wanted version. Validation used by
#        CI
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2021 Scrutiny Debugger

set -euo pipefail

source $(dirname ${BASH_SOURCE[0]})/common.sh
shopt -s nocasematch

if [ $# -eq 0 ]; then
    fatal "Python version must be specified"
fi

REQUIRED_VERSION=$1
ACTUAL_PYTHON_VERSION=$(python3 --version)
ACTUAL_PIP_VERSION=$(pip3 --version)

if [[ $ACTUAL_PYTHON_VERSION != *"python ${REQUIRED_VERSION}"* ]]; then
    fatal "Reported python3 version is ${ACTUAL_PYTHON_VERSION}. Expecting Python ${REQUIRED_VERSION}"
fi

if [[ $ACTUAL_PIP_VERSION != *"python ${REQUIRED_VERSION}"* ]]; then 
    fatal "Reported pip3 version is ${ACTUAL_PIP_VERSION}. Expecting pip for Python ${REQUIRED_VERSION}"
fi

info "Python version OK."
info "  - ${ACTUAL_PYTHON_VERSION}"
info "  - ${ACTUAL_PIP_VERSION}"
exit 0
