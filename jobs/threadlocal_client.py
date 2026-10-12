"""Thread-local wrapper for Supabase clients.

The API runs inside a thread pool. One shared supabase-py/httpx client used from several threads at once can fail with
`[Errno 11] Resource temporarily unavailable`. This proxy gives every thread its own real client (created lazily from
the same factory) while presenting the same attribute surface (`.table()`, `.rpc()`, `.storage`, ...).
"""
from __future__ import annotations

import threading
from typing import Any, Callable


class ThreadLocalClient:
    def __init__(self, factory: Callable[[], Any]) -> None:
        self._factory = factory
        self._local = threading.local()

    def _real(self) -> Any:
        c = getattr(self._local, "client", None)
        if c is None:
            c = self._factory()
            self._local.client = c
        return c

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real(), name)
