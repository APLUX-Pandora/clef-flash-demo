"""Load the installed native SDK."""
import ctypes
from functools import lru_cache
from pathlib import Path

from pandora_runtime._native import library as runtime_library


def library_path():
    return Path(__file__).resolve().parent / "lib/libclef.so"


@lru_cache(maxsize=1)
def library():
    runtime_library()
    return ctypes.CDLL(str(library_path()))
