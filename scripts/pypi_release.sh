#!/bin/bash

#    pypi_release.sh
#        Make a PyPi release ad push it to PyPi
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

set -eEuo pipefail
source $(dirname ${BASH_SOURCE[0]})/common.sh

PROJECT_ROOT="$(get_project_root)"
cd "$PROJECT_ROOT"

trap 'fatal "Exited with status $? at line $LINENO"' ERR 

[ -z ${1:+x} ] && fatal "Missing version argument"

version="$1"

git_diff="$(git diff --shortstat)"
git_diff_cached="$(git diff --shortstat --cached)"

[ -z "$git_diff" ] || fatal "Uncomitted changes on repo"
[ -z "$git_diff_cached" ] || fatal "Staging changes on repo"

tag=$( { git tag -l --points-at HEAD || true; } | grep $version)
code_version=$(cat scrutiny/__init__.py | grep -E ^[[:space:]]*__version__  | sed -r "s/__version__[[:space:]]*=[[:space:]]*'([^']+)'/\1/")
assert_scrutiny_version_format "$code_version"

[ "$version" != "$tag" ] && fatal "Tag of HEAD does not match given version. Expected '$version'"
[ "$version" != "v$code_version" ] && fatal "Code version does not match given version : 'v$code_version' vs '$version'"

rm -rf build dist *.egg-info
python3 -m build

read -p "Everything seems alright. Upload? "

proceed=0
 
[ "${REPLY,,}" == "yes" ] && proceed=1
[ "${REPLY,,}" == "y" ] && proceed=1

[ $proceed -ne 1 ] && { info "Not uploading"; exit; }
python -m twine upload dist/*
success "Uploaded to PyPi"
