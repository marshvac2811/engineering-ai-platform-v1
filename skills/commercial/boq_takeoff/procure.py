"""Consolidate the 'procure as specified' BOQ lines (equipment and lump-sum items) into one grouped purchase list."""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

# Ordered rules: the first group whose pattern matches the item title wins.
_GROUPS = [
    ("Fire protection devices and systems", r"sprinkler|smoke detector|extinguisher|landing valve|hose reel|fire pump|fire alarm"),
    ("Plumbing fixtures, tanks and pumps", r"water closet|urinal|wash basin|water storage tank|transfer pump"),
    ("Lighting, power and distribution", r"light fitting|led panel light|socket outlet|distribution board|lt panel"),
    ("Chilled water plant", r"chilled water plant"),
    ("Controls, BMS and instrumentation", r"controller|automation|automatic control|control.{0,3}optimi|\bbms\b|\bddc\b|sensor|actuator|thermostat"),
    ("VFDs, starters and electrical panels", r"^[^|]{0,30}\bvfd\b|variable frequency|starter|\bpanel|\bmcc\b|switchgear"),
    ("Chillers, heat pumps and cooling towers", r"chiller|cooling tower|fouling factor|heat pump"),
    ("Pumps, tanks and hydronic accessories", r"pump|expansion tank|separator|degasser|deaerator|strainer|valve|picv|flow meter|skid|ball trap|ball collector"),
    ("Air handling units, fans and air cleaning", r"\bahu\b|\bahus\b|air handling|\bfans?\b|air cleaner|air washer|ionis|ioniz|filter|casing leakage|eurovent"),
    ("Split units and terminal units", r"split|hi.?wall|fan coil|\bfcu\b|cassette|vrf"),
]
OTHER = "Other equipment and lump-sum items"
ORDER = [g for g, _ in _GROUPS] + [OTHER]


def canonical_unit(unit: Any) -> str:
    u = re.sub(r"[^a-z]", "", str(unit or "").lower())
    if u in ("each", "no", "nos", "number", "numbers", "unit", "units", "pcs", "piece", "pieces"):
        return "Nos"
    if u in ("set", "sets"):
        return "Set"
    if u in ("lot", "lots", "ls", "lumpsum"):
        return "Lot"
    return str(unit or "").strip() or "-"


def group_for(description: str) -> str:
    text = " ".join(str(description or "").split())
    title = text.split(" | ")[0][:200]
    for name, pat in _GROUPS:
        if re.search(pat, title, re.I):
            return name
    low = text[:400]
    for name, pat in _GROUPS:
        if re.search(pat, low, re.I):
            return name
    return OTHER


def consolidate_procure(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge lines with the same description and unit (quantities added), group them, and list the BOQ items behind each line."""
    merged: Dict[tuple, Dict[str, Any]] = {}
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        desc = " ".join(str(r.get("description") or "").split())
        unit = canonical_unit(r.get("unit"))
        key = (desc.lower(), unit)
        try:
            qty = float(r.get("quantity") or 0)
        except (TypeError, ValueError):
            qty = 0.0
        cur = merged.setdefault(key, {"group": group_for(desc), "description": desc, "unit": unit, "quantity": 0.0, "item_nos": [], "lines_merged": 0})
        cur["quantity"] = round(cur["quantity"] + qty, 3)
        cur["item_nos"].append(str(r.get("item_no")))
        cur["lines_merged"] += 1
    out = list(merged.values())
    out.sort(key=lambda x: (ORDER.index(x["group"]) if x["group"] in ORDER else len(ORDER), x["description"].lower()))
    for x in out:
        x["item_nos"] = ", ".join(x["item_nos"])
    return out
