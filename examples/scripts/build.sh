#!/bin/bash
set -euo pipefail

FIRMWARE_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. >/dev/null 2>&1 && pwd -P )"
BUILD_ROOT="$FIRMWARE_ROOT/build"

mkdir -p "$BUILD_ROOT"

cmake \
    -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_VERBOSE_MAKEFILE=TRUE \
    -S "$FIRMWARE_ROOT" \
    -B "$BUILD_ROOT"

cmake --build "$BUILD_ROOT" --target all -- -l`nproc`
