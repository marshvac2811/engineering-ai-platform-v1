"""Deterministic room-schedule extraction from text, plus closed-polyline rooms from ASCII DXF.

Text: only rows that state a room name and an area (with a unit) are returned; areas in sq ft are converted.
DXF: a closed polyline with exactly one TEXT/MTEXT label inside is reported as a CANDIDATE room (area from
geometry, units from $INSUNITS). Candidates are flagged inferred and need human confirmation; nothing is
guessed when units are unknown or labels are missing/ambiguous.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

SQFT_TO_SQM = 0.09290304
_NUM = r"([0-9][0-9,]*(?:\.[0-9]+)?)"
_AREA_UNIT = r"(m2|m²|sqm|sq\.?\s*m|sqft|sq\.?\s*ft|sft|ft2|ft²)"
_AREA_IN_TEXT = re.compile(_NUM + r"\s*" + _AREA_UNIT + r"\b", re.I)
_OCC = re.compile(r"(?:occupancy|occupants?|persons?|pax|people|capacity)\s*[:=-]?\s*(\d+)|\b(\d+)\s*(?:persons?|pax|people|occupants?)\b", re.I)
_LABEL_AREA = re.compile(r"\barea\s*[:=-]?\s*" + _NUM + r"\s*" + _AREA_UNIT + r"\b", re.I)
_SKIP_NAME = re.compile(r"^(?:total|sub[- ]?total|grand total|s\.?\s*no\.?|sr\.?\s*no\.?|room(?:\s*name)?|name|area|description|item)$", re.I)


def _to_m2(value: str, unit: str) -> float:
    v = float(value.replace(",", ""))
    u = re.sub(r"[\s.]", "", unit.lower())
    return v * SQFT_TO_SQM if u in {"sqft", "sft", "ft2", "ft²"} else v


def extract_room_schedule(text: str) -> Dict[str, Any]:
    rooms: List[Dict[str, Any]] = []
    skipped: List[str] = []
    seen = set()
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        m_label = re.match(r"(?i)^\s*(?:room|space)\s*[:=-]\s*([^|,;]+?)\s*(?:[|,;].*)?$", line)
        am = _LABEL_AREA.search(line) or _AREA_IN_TEXT.search(line)
        if not am:
            if m_label or re.match(r"(?i)^\s*(?:room|space)\b", line):
                skipped.append(f"No area with a unit on line: {line[:80]}")
            continue
        area_m2 = _to_m2(am.group(1), am.group(2))
        if area_m2 <= 0:
            skipped.append(f"Non-positive area on line: {line[:80]}")
            continue
        if m_label:
            name = m_label.group(1).strip()
        else:
            head = line[: am.start()]
            head = re.sub(r"(?i)\barea\s*[:=-]?\s*$", "", head)
            parts = [p.strip() for p in re.split(r"\s*[|;,\t]\s*|\s{2,}", head) if p.strip()]
            parts = [p for p in parts if not re.fullmatch(r"[A-Za-z]{0,3}[- ]?\d{1,3}\.?", p)] or parts
            name = parts[-1] if parts else ""
        name = re.sub(r"\s+", " ", name).strip(" :-")
        if not name or _SKIP_NAME.match(name):
            continue
        occ_m = _OCC.search(line)
        occ = int(next(g for g in occ_m.groups() if g)) if occ_m else None
        key = (name.lower(), round(area_m2, 2))
        if key in seen:
            continue
        seen.add(key)
        room: Dict[str, Any] = {"name": name, "area_m2": round(area_m2, 2), "source_text": line[:160]}
        if occ is not None:
            room["occupancy"] = occ
        rooms.append(room)
    return {"rooms": rooms, "skipped": skipped}


# ---------------------------------------------------------------- DXF
_INSUNITS_TO_M = {1: 0.0254, 2: 0.3048, 4: 0.001, 5: 0.01, 6: 1.0}


def _pairs(data: bytes) -> List[Tuple[str, str]]:
    lines = data.decode("utf-8-sig", errors="replace").splitlines()
    return [(lines[i].strip(), lines[i + 1].strip()) for i in range(0, len(lines) - 1, 2)]


def _entities(pairs):
    out, i = [], 0
    while i < len(pairs):
        if pairs[i] == ("0", "LWPOLYLINE") or pairs[i][0] == "0" and pairs[i][1] in ("TEXT", "MTEXT"):
            kind, j, rec = pairs[i][1], i + 1, []
            while j < len(pairs) and pairs[j][0] != "0":
                rec.append(pairs[j])
                j += 1
            out.append((kind, rec))
            i = j
        else:
            i += 1
    return out


def _polygon_area(pts):
    s = 0.0
    for k in range(len(pts)):
        x1, y1 = pts[k]
        x2, y2 = pts[(k + 1) % len(pts)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def _inside(pt, poly):
    x, y = pt
    c = False
    for k in range(len(poly)):
        x1, y1 = poly[k]
        x2, y2 = poly[(k + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def extract_dxf_candidate_rooms(data: bytes) -> Dict[str, Any]:
    pairs = _pairs(data)
    units_code = None
    for k, (c, v) in enumerate(pairs):
        if c == "9" and v == "$INSUNITS" and k + 1 < len(pairs):
            try:
                units_code = int(pairs[k + 1][1])
            except ValueError:
                pass
    warnings: List[str] = []
    factor = _INSUNITS_TO_M.get(units_code or 0)
    if factor is None:
        warnings.append("Drawing units ($INSUNITS) are missing or unsupported, so areas cannot be converted to m2; no candidate rooms were produced.")
    polys, labels = [], []
    for kind, rec in _entities(pairs):
        if kind == "LWPOLYLINE":
            closed = any(c == "70" and int(v) & 1 for c, v in rec if v.lstrip("-").isdigit())
            xs = [float(v) for c, v in rec if c == "10"]
            ys = [float(v) for c, v in rec if c == "20"]
            if closed and len(xs) == len(ys) and len(xs) >= 3:
                polys.append(list(zip(xs, ys)))
        else:
            d = dict(rec)
            try:
                labels.append((str(d.get("1", "")).strip(), (float(d["10"]), float(d["20"]))))
            except (KeyError, ValueError):
                continue
    candidates, unlabeled, ambiguous = [], 0, 0
    if factor is not None:
        for poly in polys:
            inside = [t for t, p in labels if t and _inside(p, poly)]
            if len(inside) == 0:
                unlabeled += 1
                continue
            if len(inside) > 1:
                ambiguous += 1
                continue
            area_m2 = _polygon_area(poly) * factor * factor
            candidates.append({"name": inside[0], "area_m2": round(area_m2, 2), "inferred": True, "review_required": True,
                               "basis": "Area of a closed polyline containing exactly one text label; layer semantics not checked."})
    if unlabeled:
        warnings.append(f"{unlabeled} closed polyline(s) had no text label inside and were ignored.")
    if ambiguous:
        warnings.append(f"{ambiguous} closed polyline(s) contained more than one text label and were ignored.")
    return {"rooms": candidates, "units_code": units_code, "warnings": warnings}
