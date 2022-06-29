#!/bin/bash

shopt -s nocasematch

VERSION=$1
if [[ $(python3 --version) != *"python ${VERSION}"* ]]; then
    echo "Reported python3 version is "
    python3 --version
    exit 1
fi

if [[ $(pip3 --version) != *"python ${VERSION}"* ]]; then 
    echo "Reported pip3 version is "
    pip3 --version
    exit 1
fi

exit 0