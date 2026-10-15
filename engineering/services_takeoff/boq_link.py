"""Tie BOQ item descriptions to what was measured on the services drawing, and turn the measurement into material lists."""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Tuple

from engineering.services_takeoff.measure import Measurement, parse_size, size_width_mm

# --- starting factors (disclosed in the report as assumptions; override through the `drawing_factors` input)
DEFAULTS: Dict[str, float] = {
    "pipe_wastage_pct": 5.0, "pipe_length_m": 3.0, "duct_allowance_pct": 10.0, "duct_hanger_spacing_m": 2.4, "duct_joint_spacing_m": 1.2,
    "conduit_wastage_pct": 5.0, "conduit_length_m": 3.0, "conduit_saddle_spacing_m": 1.0, "wires_per_conduit": 3.0, "wire_wastage_pct": 10.0,
    "tray_length_m": 2.5, "tray_support_spacing_m": 1.5, "tray_wastage_pct": 5.0, "insulation_wastage_pct": 5.0,
}
_FIXTURE_WORDS: List[Tuple[str, re.Pattern]] = [
    ("water_closet", re.compile(r"(water\s*closet|\bwc\b|\bewc\b|\biwc\b)", re.I)), ("wash_basin", re.compile(r"(wash\s*basin|lavatory)", re.I)),
    ("urinal", re.compile(r"urinal", re.I)), ("shower", re.compile(r"shower", re.I)), ("floor_drain", re.compile(r"(floor\s*drain|gully)", re.I)),
    ("sprinkler_head", re.compile(r"sprinkler\s*head", re.I)), ("smoke_detector", re.compile(r"(smoke|heat)\s*detector", re.I)),
    ("diffuser", re.compile(r"(diffuser|grille)", re.I)), ("light_point", re.compile(r"(light\s*fitting|luminaire|light\s*point|downlight)", re.I)),
    ("socket", re.compile(r"(socket|power\s*outlet)", re.I)), ("switch", re.compile(r"\bswitch\b", re.I)), ("sink", re.compile(r"\bsink\b", re.I)),
]
_METRIC_UNITS = {"m", "rm", "rmt", "rmtr", "mtr", "mtrs", "meter", "meters", "metre", "metres", "mt"}
_PROGRAMME = {  # recipe id used so the work programme can schedule drawing-based items
    "drawing_plumbing_pipe": "plumbing_pipe", "drawing_fire_pipe": "fire_pipe", "drawing_hvac_pipe": "hvac_pipe", "drawing_hvac_duct": "hvac_duct",
    "drawing_duct_insulation": "duct_insulation", "drawing_conduit": "conduit", "drawing_wiring": "wiring", "drawing_cable_tray": "cable_tray",
}


def classify_line(description: str) -> Optional[Dict[str, Any]]:
    d = str(description or "").lower()
    size = parse_size(description)
    if any(rx.search(d) for _k, rx in _FIXTURE_WORDS) and re.search(r"(supply|provid|fix|install|fitting)", d):
        for kind, rx in _FIXTURE_WORDS:
            if rx.search(d):
                return {"kind": "fixture", "device": kind, "size": None}
    if re.search(r"(insulat)", d) and re.search(r"\bduct", d):
        return {"kind": "duct_insulation", "category": "hvac_duct", "size": size}
    if re.search(r"(sprinkler|fire\s*fight|fire\s*hydrant|hydrant|fire\s*main|fire\s*protection)", d) and re.search(r"(pipe|piping|main|riser|header)", d):
        return {"kind": "pipe", "category": "fire_pipe", "size": size}
    if re.search(r"\bduct(ing|s)?\b", d) and not re.search(r"(cable|conduit)", d):
        return {"kind": "duct", "category": "hvac_duct", "size": size}
    if re.search(r"(cable\s*tray|trunking)", d):
        return {"kind": "tray", "category": "cable_tray", "size": size}
    if re.search(r"(wire|wiring)", d) and not re.search(r"(armoured|xlpe)", d):
        return {"kind": "wiring", "category": "conduit", "size": None}
    if re.search(r"conduit", d):
        return {"kind": "conduit", "category": "conduit", "size": size}
    if re.search(r"(chilled|condenser|chw|refrigerant)", d) and re.search(r"(pipe|piping)", d):
        return {"kind": "pipe", "category": "hvac_pipe", "size": size}
    if re.search(r"(pipe|piping|cpvc|upvc|ppr|swr|water\s*supply|soil|waste|drainage)", d) and not re.search(r"(duct|cable)", d):
        return {"kind": "pipe", "category": "plumbing_pipe", "size": size}
    return None


def _metres(qty: float, unit: str) -> Optional[float]:
    u = re.sub(r"\s+", "", str(unit or "").lower())
    if u in _METRIC_UNITS:
        return qty
    if u in ("rft", "ft"):
        return qty * 0.3048
    return None


def _perimeter_m(size: str) -> Optional[float]:
    w = size_width_mm(size)
    if w is None:
        return None
    return (2 * (w[0] + w[1]) if w[1] else math.pi * w[0]) / 1000.0


def _spacing_for(size: str, base: float) -> float:
    w = size_width_mm(size)
    d = w[0] if w else 50
    return 1.2 if d <= 25 else 1.5 if d <= 50 else 2.0 if d <= 100 else 3.0


def _mat(name, unit, qty, basis):
    return {"material_name": name, "unit": unit, "quantity": round(float(qty), 3), "basis": basis}


def materials_for(kind: str, category: str, sizes: List[str], meas: Measurement, f: Dict[str, float]) -> Tuple[List[Dict[str, Any]], float, str]:
    """Returns (materials, main quantity, main unit)."""
    mats: List[Dict[str, Any]] = []
    main, main_unit = 0.0, "m"
    label = {"plumbing_pipe": "Pipe", "fire_pipe": "Fire pipe", "hvac_pipe": "HVAC pipe", "conduit": "Conduit", "cable_tray": "Cable tray", "hvac_duct": "Duct"}[category]
    for sz in sizes:
        L = meas.length(category, sz)
        if L <= 0:
            continue
        fc = meas.fitting_counts(category, sz)
        tag = f" DN{sz}" if category.endswith("pipe") and sz != "unsized" else (f" {sz} mm" if sz != "unsized" else " (size not labelled)")
        e90, e45, tee, cross, red, end = (fc.get(k, 0) for k in ("elbow_90", "elbow_45", "tee", "cross", "reducer", "end"))
        if kind in ("pipe",):
            w = f["pipe_wastage_pct"]
            mats.append(_mat(f"{label}{tag}", "m", L * (1 + w / 100), f"{L:.2f} m measured on drawing + {w:g}% wastage"))
            for nm, n in ((f"Elbow 90{tag}", e90), (f"Elbow 45{tag}", e45), (f"Tee{tag}", tee), (f"Cross{tag}", cross), (f"Reducer{tag}", red),
                          (f"End connection (cap / adaptor / valve){tag}", end)):
                if n:
                    mats.append(_mat(nm, "nos", n, "counted from the drawing geometry"))
            mats.append(_mat(f"Coupling{tag}", "nos", max(0, math.ceil(L / f["pipe_length_m"]) - 1), f"one joint per {f['pipe_length_m']:g} m pipe length"))
            sp = _spacing_for(sz, 1.5)
            mats.append(_mat(f"Pipe clamp / support{tag}", "nos", math.ceil(L / sp), f"one support per {sp:g} m of run"))
            main += L
        elif kind in ("duct", "duct_insulation"):
            per = _perimeter_m(sz)
            if per is None:
                mats.append(_mat(f"Duct{tag}: length only", "m", L, "size not labelled, so sheet area cannot be worked out"))
                main += L
                continue
            area = L * per
            if kind == "duct_insulation":
                w = f["insulation_wastage_pct"]
                mats.append(_mat(f"Duct insulation{tag} (thickness as specified)", "sqm", area * (1 + w / 100), f"{L:.2f} m x perimeter {per:.2f} m + {w:g}% wastage"))
            else:
                a = f["duct_allowance_pct"]
                mats.append(_mat(f"GI sheet for duct{tag} (gauge as per size/specification)", "sqm", area * (1 + a / 100), f"{L:.2f} m x perimeter {per:.2f} m + {a:g}% for bends, tees and wastage"))
                for nm, n in ((f"Duct elbow 90{tag} (made from the sheet above)", e90), (f"Duct elbow 45{tag} (made from the sheet above)", e45),
                              (f"Duct tee / branch{tag} (made from the sheet above)", tee + cross), (f"Duct reducer{tag} (made from the sheet above)", red)):
                    if n:
                        mats.append(_mat(nm, "nos", n, "counted from the drawing geometry (information; sheet already included)"))
                joints = math.ceil(L / f["duct_joint_spacing_m"])
                mats.append(_mat(f"Flange / duct joint{tag}", "nos", joints, f"one joint per {f['duct_joint_spacing_m']:g} m"))
                mats.append(_mat(f"Joint gasket{tag}", "m", joints * per, "joints x duct perimeter"))
                mats.append(_mat(f"Duct hanger / support{tag}", "nos", math.ceil(L / f["duct_hanger_spacing_m"]), f"one hanger per {f['duct_hanger_spacing_m']:g} m"))
            main += area
            main_unit = "sqm"
        elif kind == "conduit":
            w = f["conduit_wastage_pct"]
            mats.append(_mat(f"Conduit{tag}", "m", L * (1 + w / 100), f"{L:.2f} m measured on drawing + {w:g}% wastage"))
            if e90 + e45:
                mats.append(_mat(f"Conduit bend{tag}", "nos", e90 + e45, "counted from the drawing geometry"))
            if tee + cross:
                mats.append(_mat(f"Junction box / inspection tee{tag}", "nos", tee + cross, "at each branch point on the drawing"))
            mats.append(_mat(f"Coupling{tag}", "nos", max(0, math.ceil(L / f["conduit_length_m"]) - 1), f"one joint per {f['conduit_length_m']:g} m"))
            mats.append(_mat(f"Saddle / clip{tag}", "nos", math.ceil(L / f["conduit_saddle_spacing_m"]), f"one per {f['conduit_saddle_spacing_m']:g} m"))
            main += L
        elif kind == "wiring":
            n = f["wires_per_conduit"]
            w = f["wire_wastage_pct"]
            mats.append(_mat(f"Wire in conduit{tag} ({n:g} wires per run; size as specified)", "m", L * n * (1 + w / 100), f"{L:.2f} m of conduit x {n:g} wires + {w:g}% wastage"))
            main += L * n
        elif kind == "tray":
            w = f["tray_wastage_pct"]
            mats.append(_mat(f"Cable tray{tag}", "m", L * (1 + w / 100), f"{L:.2f} m measured on drawing + {w:g}% wastage"))
            for nm, n in ((f"Tray bend{tag}", e90 + e45), (f"Tray tee{tag}", tee), (f"Tray cross{tag}", cross), (f"Tray reducer{tag}", red)):
                if n:
                    mats.append(_mat(nm, "nos", n, "counted from the drawing geometry"))
            mats.append(_mat(f"Tray coupler / splice plate{tag}", "nos", max(0, math.ceil(L / f["tray_length_m"]) - 1), f"one joint per {f['tray_length_m']:g} m"))
            mats.append(_mat(f"Tray support bracket{tag}", "nos", math.ceil(L / f["tray_support_spacing_m"]), f"one per {f['tray_support_spacing_m']:g} m"))
            main += L
    return mats, main, main_unit


def apply_drawing(result: Dict[str, Any], lines: List[Dict[str, Any]], meas: Measurement, *, factors: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    f = dict(DEFAULTS)
    for k, v in (factors or {}).items():
        try:
            if k in f and float(v) > 0:
                f[k] = float(v)
        except (TypeError, ValueError):
            pass
    breakdown: List[Dict[str, Any]] = list(result.get("boq_breakdown") or [])
    by_item = {str(b["item_no"]): b for b in breakdown}
    notes: List[str] = []
    claims: List[Tuple[str, Dict[str, Any], Dict[str, Any]]] = []
    for n, line in enumerate(lines, 1):
        item = str(line.get("item_no") or n)
        cl = classify_line(str(line.get("description", "")))
        if cl:
            claims.append((item, line, cl))
    # which measured sizes are claimed by a size-specific BOQ line
    claimed: Dict[str, set] = {}
    for item, line, cl in claims:
        cat = cl.get("category")
        if cat and cl.get("size") and cl["size"] in meas.sizes(cat):
            claimed.setdefault(cat, set()).add(cl["size"])
    taken: Dict[str, str] = {}     # kind key -> item that already took off the remaining sizes
    covered: List[str] = []
    for item, line, cl in claims:
        try:
            qty = float(str(line.get("quantity", "")).replace(",", ""))
        except ValueError:
            qty = 0.0
        unit = str(line.get("unit") or "")
        desc = str(line.get("description", ""))
        if cl["kind"] == "fixture":
            n = meas.devices.get(cl["device"], 0)
            key = "dev:" + cl["device"]
            if n <= 0 or key in taken:
                if n > 0:
                    notes.append(f"Item {item}: the {cl['device'].replace('_', ' ')} count on the drawing is already taken at item {taken[key]}.")
                continue
            taken[key] = item
            mats = [_mat(desc[:90], "nos", n, f"{n} symbol(s) counted on the drawing")]
            row = _row(item, line, qty, unit, f"drawing_fixture_{cl['device']}", "Counted from drawing", n, "nos", mats)
            row["drawing_note"] = f"Counted on drawing: {n} nos; BOQ quantity {qty:g} {unit}" + _variance(qty, float(n))
        else:
            cat = cl["category"]
            sizes_all = meas.sizes(cat)
            if not sizes_all:
                notes.append(f"Item {item}: no {cat.replace('_', ' ')} was found on the drawing, so the catalogue recipe (if any) was used.")
                continue
            if cl.get("size"):
                sizes = [cl["size"]] if cl["size"] in sizes_all else []
                if not sizes:
                    notes.append(f"Item {item}: the BOQ asks for size {cl['size']} but the drawing has sizes {', '.join(sizes_all)} for this service.")
                    continue
            else:
                key = "svc:" + cl["kind"] + ":" + cat
                if key in taken:
                    notes.append(f"Item {item}: the unsized {cat.replace('_', ' ')} on the drawing was already taken off at item {taken[key]}; add a size to this item to split them.")
                    continue
                taken[key] = item
                sizes = [s for s in sizes_all if s not in claimed.get(cat, set())] or sizes_all
            mats, main, main_unit = materials_for(cl["kind"], cat, sizes, meas, f)
            if not mats:
                continue
            rid = {"pipe": {"plumbing_pipe": "drawing_plumbing_pipe", "fire_pipe": "drawing_fire_pipe", "hvac_pipe": "drawing_hvac_pipe"}.get(cat),
                   "duct": "drawing_hvac_duct", "duct_insulation": "drawing_duct_insulation", "conduit": "drawing_conduit", "wiring": "drawing_wiring", "tray": "drawing_cable_tray"}[cl["kind"]]
            row = _row(item, line, qty, unit, rid, "Measured from drawing", main, main_unit, mats)
            L = sum(meas.length(cat, s) for s in sizes)
            comp = _metres(qty, unit)
            if cl["kind"] in ("duct_insulation",) or (cl["kind"] == "duct" and main_unit == "sqm"):
                txt = f"Measured on drawing: {L:.1f} m of run ({main:.1f} sqm of duct surface); sizes {', '.join(sizes)}"
                cmp_ = None if re.sub(r"\s+", "", unit.lower()) not in ("sqm", "m2", "sqmt", "sq.m") else main
                txt += f"; BOQ quantity {qty:g} {unit}" + (_variance(qty, cmp_) if cmp_ else "")
            else:
                txt = f"Measured on drawing: {L:.1f} m ({', '.join(sizes)}); BOQ quantity {qty:g} {unit}" + (_variance(comp, L) if comp is not None else "")
            row["drawing_note"] = txt
        covered.append(item)
        if item in by_item:
            idx = breakdown.index(by_item[item])
            breakdown[idx] = row
        else:
            breakdown.append(row)
        by_item[item] = row
    if not covered:
        result.setdefault("drawing_notes", notes)
        return result
    # rebuild the flat tables, totals and exception lists from the final per-item blocks
    totals: Dict[Tuple[str, str], Dict[str, Any]] = {}
    flat, takeoff = [], []
    for b in breakdown:
        takeoff.append({k: v for k, v in b.items() if k not in ("materials", "drawing_note")})
        for m_ in b["materials"]:
            flat.append({"item_no": b["item_no"], "recipe_name": b["recipe_name"], **m_})
            key = (m_["material_name"].strip().lower(), m_["unit"].strip().lower())
            cur = totals.setdefault(key, {"material_name": m_["material_name"], "unit": m_["unit"], "quantity": 0.0, "source_items": ""})
            cur["quantity"] = round(cur["quantity"] + float(m_["quantity"]), 3)
            cur["source_items"] = (cur["source_items"] + ", " + str(b["item_no"])) if cur["source_items"] else str(b["item_no"])
    cov = set(covered)
    result["boq_breakdown"], result["line_takeoff"], result["line_materials"] = breakdown, takeoff, flat
    result["material_totals"] = sorted(totals.values(), key=lambda r: r["material_name"].lower())
    result["unmatched_lines"] = [u for u in result.get("unmatched_lines", []) if str(u.get("item_no")) not in cov]
    result["procure_as_specified"] = [p for p in result.get("procure_as_specified", []) if str(p.get("item_no")) not in cov]
    result["procure_as_specified_count"] = len(result["procure_as_specified"])
    result["unmatched_line_count"] = len(result["unmatched_lines"])
    result["matched_line_count"] = len(breakdown)
    result["drawing_measured_item_count"] = len(covered)
    result["drawing_notes"] = notes
    return result


def _variance(boq: Optional[float], meas: Optional[float]) -> str:
    if not boq or meas is None:
        return ""
    pct = (meas - boq) / boq * 100
    return f"; drawing is {abs(pct):.0f}% {'more' if pct > 0 else 'less'} than the BOQ"


def _row(item, line, qty, unit, rid, source, main, main_unit, mats):
    return {"item_no": item, "description": str(line.get("description", "")), "boq_quantity": qty, "boq_unit": unit or main_unit,
            "recipe_id": rid, "recipe_name": source, "recipe_source": "drawing", "recipe_quantity": round(main, 3), "recipe_unit": main_unit, "materials": mats}
