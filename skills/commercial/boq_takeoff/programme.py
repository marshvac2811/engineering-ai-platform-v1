"""Indicative work programme from a BOQ takeoff: days per item, sequence, parallel working, total duration.

No prices are used anywhere. Crew output per day (per gang) is a disclosed starting value that the
requester can override per recipe (``productivity``) and the number of gangs per trade (``gangs``).
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

# recipe id -> (trade, phase no., crew output per gang-day in sqm or m or nos)
_STARTERS: Dict[str, tuple] = {
    "gi_duct_fabrication": ("HVAC", 2, 15), "cable_tray": ("Electrical", 2, 40), "mv_cable_supply": ("Electrical", 2, 150),
    "flexible_conduit": ("Electrical", 2, 80), "ms_condenser_water_pipe": ("Plumbing / Piping", 2, 12),
    "gi_drain_pipe": ("Plumbing / Piping", 2, 15), "duct_thermal_insulation": ("HVAC", 3, 40), "underdeck_insulation": ("HVAC", 3, 40),
    "fresh_air_louvers": ("HVAC", 3, 6), "non_return_damper": ("HVAC", 3, 4),
    "gypsum_wall_partition": ("Partition", 4, 12), "aluminium_partition_particle_board": ("Partition", 4, 10),
    "gypsum_false_ceiling": ("False ceiling", 5, 20), "gypsum_ceiling_tiles": ("False ceiling", 5, 40),
    "wall_tile_work": ("Tiling", 6, 10), "vitrified_tile_flooring": ("Tiling", 7, 12),
    "frameless_glass_partition": ("Glazing", 8, 8), "fire_rated_door": ("Doors", 8, 3),
    # items measured from a services drawing
    "drawing_plumbing_pipe": ("Plumbing / Piping", 2, 12), "drawing_fire_pipe": ("Fire fighting", 2, 10), "drawing_hvac_pipe": ("HVAC piping", 2, 10),
    "drawing_hvac_duct": ("HVAC", 2, 15), "drawing_duct_insulation": ("HVAC", 3, 40), "drawing_conduit": ("Electrical", 2, 40),
    "drawing_wiring": ("Electrical", 3, 150), "drawing_cable_tray": ("Electrical", 2, 40),
}
_PHASES = {1: "Civil / preparation", 2: "Services first fix", 3: "Insulation and HVAC fittings", 4: "Partitions", 5: "Ceilings",
           6: "Wall finishes", 7: "Floor finishes", 8: "Glazing, doors and joinery"}
_OVERLAP = 0.4        # next phase may start when the previous one is 40 % through (different gangs, different areas)
_AREA = {"sqm": 1.0, "sqft": 0.09290304}


def _to_output_unit(qty: float, unit: str, kind: str) -> float:
    u = (unit or "").lower()
    if kind in ("sqm",) and u in _AREA:
        return qty * _AREA[u]
    if u == "rft":
        return qty * 0.3048
    return qty


def build_programme(breakdown: List[Dict[str, Any]], *, gangs: Optional[Dict[str, Any]] = None, productivity: Optional[Dict[str, Any]] = None,
                    working_days_per_week: int = 6, start_date: Optional[str] = None) -> Dict[str, Any]:
    gangs = {str(k).lower(): max(1, int(v)) for k, v in (gangs or {}).items()}
    productivity = {str(k): float(v) for k, v in (productivity or {}).items() if float(v) > 0}
    wd = 6 if int(working_days_per_week or 6) >= 6 else 5
    items: List[Dict[str, Any]] = []
    skipped: List[str] = []
    for b in breakdown:
        rid_ = str(b.get("recipe_id"))
        meta = _STARTERS.get(rid_) or (("Fixtures and devices", 7, 8) if rid_.startswith("drawing_fixture_") else None)
        if meta is None:
            skipped.append(str(b.get("item_no")))
            continue
        trade, phase, out = meta
        out = productivity.get(str(b.get("recipe_id")), out)
        ru = str(b.get("recipe_unit") or "")
        qty = _to_output_unit(float(b.get("recipe_quantity") or 0), ru, "sqm" if ru.lower() in _AREA else "m")
        g = gangs.get(trade.lower(), 1)
        days = max(1, math.ceil(qty / (out * g))) if qty > 0 else 1
        items.append({"item_no": str(b.get("item_no")), "description": str(b.get("description") or ""), "trade": trade, "phase": phase,
                      "quantity": b.get("boq_quantity"), "unit": b.get("boq_unit"), "work_days": days, "gangs": g})
    if not items:
        return {"rows": [], "skipped": skipped, "total_days": 0}
    items.sort(key=lambda r: r["phase"])
    trade_free: Dict[str, int] = {}
    by_phase: Dict[int, List[Dict[str, Any]]] = {}
    phases = sorted({r["phase"] for r in items})
    for it in items:
        idx = phases.index(it["phase"])
        prev = by_phase.get(phases[idx - 1], []) if idx else []
        earliest, driver = 1, None
        for p in prev:
            s = p["start"] + math.ceil(_OVERLAP * p["work_days"])
            if s > earliest:
                earliest, driver = s, p
        free = trade_free.get(it["trade"], 1)
        if free > earliest:
            earliest, driver = free, it.get("_trade_last", driver)
        it["start"] = earliest
        it["end"] = max(it["start"] + it["work_days"] - 1, (max(p["end"] for p in prev) + 1) if prev else 0)
        it["driver"] = driver
        trade_free[it["trade"]] = it["end"] + 1
        by_phase.setdefault(it["phase"], []).append(it)
        for o in items:   # next item of the same trade waits for this one: remember it for the critical-path chain
            if o["trade"] == it["trade"]:
                o["_trade_last"] = it
    total = max(r["end"] for r in items)
    node = max(items, key=lambda r: r["end"])
    crit = set()
    while node is not None and id(node) not in crit:
        crit.add(id(node))
        node = node.get("driver")
    rows = []
    for it in items:
        after = (it["driver"]["item_no"] if it.get("driver") else "-")
        rows.append({"item_no": it["item_no"], "description": it["description"][:90], "trade": it["trade"], "stage": _PHASES[it["phase"]],
                     "quantity": it["quantity"], "unit": it["unit"], "gangs": it["gangs"], "duration_days": it["end"] - it["start"] + 1,
                     "start_day": it["start"], "end_day": it["end"], "starts_after_item": after, "critical_path": "Yes" if id(it) in crit else "-"})
    rows.sort(key=lambda r: (r["start_day"], r["end_day"]))
    out = {"rows": rows, "skipped": skipped, "total_days": total}
    if start_date:
        try:
            d0 = date.fromisoformat(str(start_date)[:10])
            def cal(n: int) -> str:
                d, left = d0, n - 1
                while left > 0 or (wd == 6 and d.weekday() == 6) or (wd == 5 and d.weekday() >= 5):
                    d += timedelta(days=1)
                    if (wd == 6 and d.weekday() == 6) or (wd == 5 and d.weekday() >= 5):
                        continue
                    left -= 1
                return d.isoformat()
            for r in rows:
                r["start_date"], r["end_date"] = cal(r["start_day"]), cal(r["end_day"])
            out["finish_date"] = cal(total)
        except ValueError:
            pass
    out["working_days_per_week"] = wd
    return out
