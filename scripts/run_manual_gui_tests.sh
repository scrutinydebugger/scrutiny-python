#!/bin/bash
set -euo pipefail

source $(dirname ${BASH_SOURCE[0]})/common.sh

PROJECT_ROOT="$(get_project_root)"
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
