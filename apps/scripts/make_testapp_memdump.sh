#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

MEMRANGE="$(python3 $SCRIPT_DIR/get_elf_memranges.py ./build/testapp/testapp)"
./build/testapp/testapp $MEMRANGE > testapp_memdump