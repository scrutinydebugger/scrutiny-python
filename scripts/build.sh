#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. >/dev/null 2>&1 && pwd -P )"
cd ${PROJECT_ROOT}

python -m nuitka                            \
    --follow-imports                        \
    --python-flag=no_asserts                \
    --python-flag=no_docstrings             \
    --report=build_output/build_report.xml  \
    --output-dir=build_output               \
    --output-filename=scrutiny_cli          \
    --nofollow-import-to=ipdb               \
    scrutiny
