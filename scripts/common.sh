#!/bin/bash

#    common.sh
#        Common tools for bash scripting
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

set -euo pipefail

RED='\033[0;31m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; NC='\033[0m'; GREEN='\033[0;32m';

success()  { >&2 echo -e "$GREEN[Success]$NC $1";}
info()  { >&2 echo -e "$CYAN[Info]$NC $1";}
warn()  { >&2 echo -e "$YELLOW[Warning]$NC $1";}
error() { >&2 echo -e "$RED[Error]$NC $1"; }
fatal() { >&2 echo -e "$RED[Fatal]$NC $1"; exit ${2:-1}; }

absnorm_exist() 
{ 
    if [ -f "$1" ]; then
        echo "$( cd "$( dirname "$1" )" >/dev/null 2>&1 && pwd -P )/$(basename "$1")"; 
    elif [ -d "$1" ]; then
        echo "$( cd "$1" >/dev/null 2>&1 && pwd -P )"; 
    else
        error "No such file or directory $1"
        return 1
    fi
    return 0
}

dir_with_default()
{
    user_input="$1"
    default="$2"

    if [ ! -z $user_input ]; then
        absnorm_exist $user_input
    else
        mkdir -p $default
        absnorm_exist $default
    fi
}

get_project_root(){
    absnorm_exist "$(dirname "${BASH_SOURCE[0]}")/.."
}

assert_dir(){
    [ -d "$1" ] || fatal "$1 is not an existing folder"
}

assert_file(){
    [ -f "$1" ] || fatal "$1 is not an existing file"
}

assert_scrutiny_version_format() {
    [[ "$1" =~ ^[0-9]\.[0-9]\.[0-9]$ ]] || fatal "Version format is not valid: ${1}"
}
