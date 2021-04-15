#!/bin/bash
set -euo pipefail

FIRMWARE_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. >/dev/null 2>&1 && pwd -P )"
BUILD_ROOT="$FIRMWARE_ROOT/build"

"$BUILD_ROOT/example/linux/linuxapp"
