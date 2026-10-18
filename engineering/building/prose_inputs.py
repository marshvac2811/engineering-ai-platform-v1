"""Read room rows and design conditions that a person types into a request.

Only values the person actually wrote are returned. Nothing is guessed.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from skills.calculators import formulas as F

_NUM = r"([0-9][0-9,]*(?:\.[0-9]+)?)"
_AREA = r"(?:m2|m²|sqm|sq\.?\s*m|sqft|sq\.?\s*ft|sft)"
# "Reception, 60 sqm, 10 people"  /  "Open office | 250 sqm | 60 pax"
_ROW = re.compile(r"^\s*(?P<name>[A-Za-z][^,|;\t\d][^,|;\t]*?|[A-Za-z][^,|;\t]*?)\s*[,|;\t]\s*" + _NUM + r"\s*(?P<unit>" + _AREA + r")\b(?P<rest>.*)$", re.I)
_PEOPLE = re.compile(r"(\d+)\s*(?:people|persons?|pax|occupants?)\b|(?:occupancy|occupants?)\s*[:=-]?\s*(\d+)", re.I)


def room_rows_from_lines(text: str) -> str:
    rows: List[str] = []
    for line in (text or "").splitlines():
        m = _ROW.match(line)
        if not m:
            continue
        name = m.group("name").strip(" -:")
        if re.search(r"(?i)\b(building|built[- ]?up|floor|total|facade|glass|wall|roof)\b", name):
            continue
        pm = _PEOPLE.search(m.group("rest"))
        occ = (pm.group(1) or pm.group(2)) if pm else None
        rows.append(f"{name} | {m.group(2)} {m.group('unit')}" + (f" | {occ} people" if occ else ""))
    return "\n".join(rows)


def _rh_from_db_wb(db: float, wb: float) -> float | None:
    if wb > db:
        return None
    lo, hi = 1.0, 100.0
    for _ in range(60):
        mid = (lo + hi) / 2
        try:
            w = F.moist_air_state(db, mid)["wet_bulb_c"]
        except Exception:
            return None
        if w > wb:
            hi = mid
        else:
            lo = mid
    return round((lo + hi) / 2, 1)


def design_conditions(text: str) -> Dict[str, float]:
    t = text or ""
    out: Dict[str, float] = {}
    m = re.search(r"(?i)outdoor[^.\n]*?" + _NUM + r"\s*°?\s*c?\s*(?:db)?\s*[/,&]\s*" + _NUM + r"\s*°?\s*c?\s*wb", t)
    if m:
        db, wb = float(m.group(1)), float(m.group(2))
        rh = _rh_from_db_wb(db, wb)
        if rh is not None:
            out["outdoor_db_c"], out["outdoor_rh_pct"] = db, rh
    m = re.search(r"(?i)indoor[^.\n]*?" + _NUM + r"\s*°?\s*c\b[^.\n]*?" + _NUM + r"\s*%\s*rh", t)
    if m:
        out["room_db_c"], out["room_rh_pct"] = float(m.group(1)), float(m.group(2))
    return out
