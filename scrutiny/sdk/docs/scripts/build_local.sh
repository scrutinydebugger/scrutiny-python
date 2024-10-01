#!/bin/bash

DOC_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." >/dev/null 2>&1 && pwd -P )"
PROJECT_ROOT=$(realpath "$DOC_ROOT/../../..")
echo $PROJECT_ROOT

cd $DOC_ROOT
PYTHONPATH=${PROJECT_ROOT}:$PYTHONPATH make html
