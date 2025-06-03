#    global_counters.py
#        A file that provide some global counter atomic counter for unique ID generation
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

__all__ = ['global_i64_counter']
import threading

int64 = 0
int64_lock = threading.Lock()


def global_i64_counter() -> int:
    """Provide a unique 64bits integer atomically. Uniqueness is guaranteed for the lifetime of the process"""
    global int64
    with int64_lock:
        v = int64
        int64 = (int64 + 1) & 0xFFFFFFFFFFFFFFFF

    return v
