#!/bin/bash

shopt -s nocasematch

VERSION=$1
if [[ $(python3 --version) != *"python ${VERSION}"* ]]; then
    exit 1
fi

if [[ $(pip3 --version) != *"python ${VERSION}"* ]]; then 
    exit 1
fi

exit 0