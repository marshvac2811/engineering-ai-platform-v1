"""Client-facing copy of an evidence bundle.

The PDF and Excel that go to clients must not reveal how quantities are worked out (recipe names, consumption and
wastage factors, calculation basis, crew-output formulas). The stored job record and the owner's dashboard keep
everything; only the rendered documents use this scrubbed copy.
"""
from __future__ import annotations

import re
from typing import Any

_SECRET_KEYS = {"recipe_id", "recipe_name", "recipe_source", "recipe_quantity", "recipe_unit", "unvalidated_recipes_used",
                "diversity_factor_pct", "cfm_per_tr", "load_method", "source_calculation", "safety_margin_pct", "people_defaults_used"}
_METHOD_WORDS = re.compile(r"rule.of.thumb|benchmark|\bnorms?\b|factor|cfm|recipe|wastage|velocity|\bcop\b|\bbasis\b|manual j|cltd|\bhap\b|starter|governed|source calculation|unvalidated", re.I)
GENERIC_NOTE = "Preliminary estimate for engineering review; not a final design. The working basis is held on the engineering file."
_DROP_ASSUMPTIONS = {"recipe_factors", "work_programme_basis"}
_TRACE_SKILLS = ("boq_takeoff", "mep_building_package")   # capabilities whose method notes and norms are not shown to clients


def _text(v: Any) -> str:
    return str(v or "")


def _scrub_warnings(items: list) -> list:
    out, dropped = [], False
    for w in items:
        t = _text(w)
        m = re.match(r"\s*(\d+) equipment or lump-sum line", t)
        if m or "procure_as_specified" in t:
            n = m.group(1) if m else ""
            out.append(f"{n} equipment or lump-sum item(s) are listed in the procure-as-specified list: buy to the BOQ specification.".strip())
        elif _METHOD_WORDS.search(t):
            dropped = True
        else:
            out.append(w)
    if dropped and GENERIC_NOTE not in out:
        out.insert(0, GENERIC_NOTE)
    return out


def _scrub_assumptions(items: list) -> list:
    """Keep only assumptions made for the client because the client did not give a value (a governance disclosure).
    Method assumptions (airflow per TR, velocities, norms, programme formulas) are never shown."""
    return [a for a in items if isinstance(a, dict) and a.get("parameter") and a.get("status")]


def _scrub(obj: Any, parent_capability: str = "") -> Any:
    if isinstance(obj, dict):
        cap = _text(obj.get("capability_id")) or parent_capability
        material_row = "material_name" in obj
        out = {}
        for k, v in obj.items():
            if k in _SECRET_KEYS or (k == "basis" and material_row):
                continue
            if k in ("calculation_trace", "calculations"):
                out[k] = []
            elif k in ("warnings", "risks_warnings", "limitations") and isinstance(v, list):
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
