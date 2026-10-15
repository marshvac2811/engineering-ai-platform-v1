"""Keep very large values (an uploaded workbook as base64, a long pasted schedule) in ONE place on a job.

A BOQ upload used to be copied 24 times into one job record (orchestration, trace, result, evidence bundle ...), making
every save and every page load move several MB and exhausting the small production server. The only full copy is
`job.inputs`; every echo elsewhere carries a short marker with the length and SHA-256 so the evidence trail still shows
exactly which value was used. `manifest.input_hash` is computed from the full inputs before any compaction.
"""
from __future__ import annotations

import hashlib
from typing import Any

LARGE_VALUE_CHARS = 20000


def marker(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()[:16]
    return f"[large value omitted: {len(value):,} characters, sha256 {digest}; full value kept only in the job inputs]"


def compact_large_values(obj: Any, limit: int = LARGE_VALUE_CHARS) -> Any:
    """Return a copy of ``obj`` with every string longer than ``limit`` replaced by a marker."""
    if isinstance(obj, str):
        return marker(obj) if len(obj) > limit else obj
    if isinstance(obj, dict):
        return {k: compact_large_values(v, limit) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [compact_large_values(v, limit) for v in obj]
    return obj
