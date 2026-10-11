"""Job / report serial numbers: YYYYMMDDHHMM (IST) + 5-digit running counter, e.g. 20261010201000001."""
from __future__ import annotations
import itertools
import threading
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
_lock = threading.Lock()
_counter = itertools.count(1)


def format_serial(moment: datetime, sequence: int) -> str:
    return moment.astimezone(IST).strftime("%Y%m%d%H%M") + f"{int(sequence):05d}"


def local_serial(moment: datetime | None = None) -> str:
    """Process-local fallback (in-memory store, tests). The database sequence is authoritative in production."""
    with _lock:
        n = next(_counter)
    return format_serial(moment or datetime.now(timezone.utc), n)
