"""Client-facing copy of an evidence bundle.

The PDF and Excel that go to clients must not reveal how quantities are worked out (recipe names, consumption and
wastage factors, calculation basis, crew-output formulas). The stored job record and the owner's dashboard keep
everything; only the rendered documents use this scrubbed copy.
"""
from __future__ import annotations

import re
from typing import Any

_SECRET_KEYS = {"recipe_id", "recipe_name", "recipe_source", "recipe_quantity", "recipe_unit", "unvalidated_recipes_used"}
_DROP_ASSUMPTIONS = {"recipe_factors", "work_programme_basis"}


def _text(v: Any) -> str:
    return str(v or "")


def _scrub_warnings(items: list) -> list:
    out = []
    for w in items:
        s = _text(w)
        if "unvalidated defaults" in s:
            continue
        m = re.match(r"\s*(\d+) equipment or lump-sum line", s)
        if m or "procure_as_specified" in s:
            n = m.group(1) if m else ""
            out.append(f"{n} equipment or lump-sum item(s) are listed in the consolidated procure-as-specified list: buy to the BOQ specification.".strip())
            continue
        out.append(w)
    return out


def _scrub_assumptions(items: list) -> list:
    out = []
    for a in items:
        if isinstance(a, dict):
            name = _text(a.get("name") or a.get("assumption")).lower().replace(" ", "_")
            if name in _DROP_ASSUMPTIONS:
                continue
        out.append(a)
    return out


def _scrub(obj: Any, parent_capability: str = "") -> Any:
    if isinstance(obj, dict):
        cap = _text(obj.get("capability_id")) or parent_capability
        material_row = "material_name" in obj
        out = {}
        for k, v in obj.items():
            if k in _SECRET_KEYS or (k == "basis" and material_row):
                continue
            if k in ("calculation_trace", "calculations") and cap == "boq_takeoff":
                out[k] = []
            elif k in ("warnings", "risks_warnings") and isinstance(v, list):
                out[k] = _scrub_warnings(v)
            elif k == "assumptions" and isinstance(v, list):
                out[k] = _scrub_assumptions(v)
            elif k == "procure_as_specified" and isinstance(v, list):
                from skills.commercial.boq_takeoff.procure import consolidate_procure
                out[k] = consolidate_procure(v) if v and "group" not in (v[0] or {}) else v
            else:
                out[k] = _scrub(v, cap)
        return out
    if isinstance(obj, list):
        return [_scrub(x, parent_capability) for x in obj]
    return obj


def client_safe_bundle(bundle: dict) -> dict:
    return _scrub(bundle or {})
