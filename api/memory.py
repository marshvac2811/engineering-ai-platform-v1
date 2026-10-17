"""Keep the free 512 MB Render instance from running out of memory.

Python's glibc allocator keeps one large memory arena per thread and rarely hands memory back, so a few big requests
(each on a different worker thread) can push the process past 512 MB even though the data itself is small.
- limit the allocator to 2 arenas (must run before worker threads start)
- hand freed memory back to the OS after every request
- log memory use after heavy requests so problems are visible in the Render logs
"""
from __future__ import annotations

import ctypes
import os
import sys

_M_ARENA_MAX = -8


def _libc():
    try:
        return ctypes.CDLL("libc.so.6")
    except OSError:
        return None


def tune_allocator(arenas: int = 2) -> bool:
    libc = _libc()
    if libc is None or not hasattr(libc, "mallopt"):
        return False
    return bool(libc.mallopt(_M_ARENA_MAX, arenas))


def trim() -> None:
    libc = _libc()
    if libc is not None and hasattr(libc, "malloc_trim"):
        try:
            libc.malloc_trim(0)
        except Exception:
            pass


def rss_mb() -> float:
    try:
        with open("/proc/self/statm") as fh:
            return int(fh.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 1e6
    except (OSError, ValueError, IndexError):
        return 0.0


class MemoryGuard:
    """WSGI wrapper: trims memory after each request and logs when usage is high."""

    def __init__(self, app, warn_mb: float = 300.0):
        self.app, self.warn_mb = app, warn_mb

    def __call__(self, environ, start_response):
        try:
            yield from self.app(environ, start_response)
        finally:
            trim()
            used = rss_mb()
            if used >= self.warn_mb:
                print(f"[memory] {environ.get('REQUEST_METHOD')} {environ.get('PATH_INFO')} rss={used:.0f}MB", file=sys.stderr, flush=True)
