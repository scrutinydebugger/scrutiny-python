#!/bin/bash

shopt -s nocasematch

VERSION=$1
ACTUAL_PYTHON_VERSION=$(python3 --version)
ACTUAL_PIP_VERSION=$(pip3 --version)

if [[ $ACTUAL_PYTHON_VERSION != *"python ${VERSION}"* ]]; then
    
    echo "ERROR - Reported python3 version is ${ACTUAL_PYTHON_VERSION}"
    exit 1
fi

if [[ $ACTUAL_PIP_VERSION != *"python ${VERSION}"* ]]; then 
    echo "ERROR - Reported pip3 version is ${ACTUAL_PIP_VERSION}"
    exit 1
fi

exit 0