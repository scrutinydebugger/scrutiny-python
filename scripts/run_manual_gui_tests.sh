#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. >/dev/null 2>&1 && pwd -P )"
MANUAL_TEST_ROOT=${PROJECT_ROOT}/test/gui/manual
FILES=$MANUAL_TEST_ROOT/*.py

for f in $FILES; do
    if [[ "$(basename $f)" = "manual_test_base.py" ]]; then
        continue
    fi
    python $f

    read -p "Continue? [y/n] " yn
    case $yn in
        [Yy]*)  ;;  
        [Nn]*) echo "Aborted" ; break ;;
    esac
done
