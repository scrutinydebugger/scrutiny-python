#!/bin/bash
absnorm() { echo "$( cd "$( dirname "$1" )" >/dev/null 2>&1 && pwd -P )/$(basename "$1")"; }

DOC_ROOT=$( absnorm "$( dirname "${BASH_SOURCE[0]}" )/.." )
PROJECT_ROOT=$(absnorm "$DOC_ROOT/../../..")
echo $PROJECT_ROOT

cd $DOC_ROOT
PYTHONPATH=${PROJECT_ROOT}:$PYTHONPATH make html
