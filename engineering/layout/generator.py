"""Concept-level HVAC and sprinkler layouts on a read plan, as an editable layered DXF (mm).

RULE-BASED AND PRELIMINARY. Equipment is positioned on a regular grid inside each room from stated spacing rules;
ducts and pipes are straight Manhattan runs drawn as centre lines. NOTHING here is sized, hydraulically checked or
clash-checked. Every spacing parameter is returned in the result so it can be shown, changed and approved.
Output is deterministic.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from shapely.geometry import Point, Polygon

from engineering.drawing.services_schematic import _finish, _new_doc
from engineering.plan.model import PlanModel, PlanRoom

DEFAULTS: Dict[str, float] = {
    "diffuser_grid_m": 3.0,          # max supply-diffuser spacing (typical comfort ceiling grid)
    "indoor_unit_area_m2": 40.0,     # one indoor unit / AHU terminal per this much floor area (concept)
    "sprinkler_max_spacing_m": 4.0,  # max spacing along and between branch lines
    "sprinkler_max_coverage_m2": 12.1,  # max floor area per head (light-hazard style; hazard class to be confirmed)
    "sprinkler_wall_max_m": 2.0,     # max distance from a wall
}
EXTRA = {"M-DIFF": 3, "M-UNIT": 4, "M-DUCT-TRUNK": 5, "F-SPKL": 1, "F-PIPE-MAIN": 6, "F-PIPE-BRANCH": 2, "A-WALL": 8, "A-ROOM": 9}


@dataclass
class LayoutResult:
    dxf: bytes
    summary: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)


def _cells(room: PlanRoom, max_pitch: float) -> List[Tuple[float, float]]:
    minx, miny, maxx, maxy = room.bounds
    poly = Polygon(room.polygon)
    nx, ny = max(1, math.ceil((maxx - minx) / max_pitch)), max(1, math.ceil((maxy - miny) / max_pitch))
    pts = []
    for i in range(nx):
        for j in range(ny):
            x, y = minx + (i + 0.5) * (maxx - minx) / nx, miny + (j + 0.5) * (maxy - miny) / ny
            if poly.contains(Point(x, y)):
                pts.append((round(x, 3), round(y, 3)))
    return pts


def _sprinkler_pitch(room: PlanRoom, p: Dict[str, float]) -> float:
    return min(p["sprinkler_max_spacing_m"], math.sqrt(p["sprinkler_max_coverage_m2"]), 2 * p["sprinkler_wall_max_m"])


def _manhattan(a: Tuple[float, float], b: Tuple[float, float]) -> List[Tuple[float, float]]:
    return [a, (b[0], a[1]), b] if a[0] != b[0] and a[1] != b[1] else [a, b]


def plan_layout(model: PlanModel, *, services: Sequence[str] = ("hvac", "fire"), plant_xy: Optional[Tuple[float, float]] = None,
                params: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    p = dict(DEFAULTS); p.update({k: float(v) for k, v in (params or {}).items() if k in DEFAULTS})
    rooms = [r for r in model.rooms if r.polygon and r.bounds]
    warnings: List[str] = []
    if not rooms:
        raise ValueError("The plan has no room geometry, so a layout cannot be drawn. A room schedule alone is not enough.")
    minx, miny, maxx, maxy = model.bounds or (min(r.bounds[0] for r in rooms), min(r.bounds[1] for r in rooms), max(r.bounds[2] for r in rooms), max(r.bounds[3] for r in rooms))
    plant = plant_xy or (round(minx - 1.5, 3), round(miny - 1.5, 3))
    if plant_xy is None:
        warnings.append("Plant/riser position not given; a point outside the lower-left corner of the plan was used. Move it to the real plant room or shaft.")
    out: Dict[str, Any] = {"params": p, "plant_xy": plant, "rooms": [], "warnings": warnings}
    for r in rooms:
        item: Dict[str, Any] = {"room_id": r.room_id, "name": r.name, "area_m2": r.area_m2}
        if "hvac" in services:
            diff = _cells(r, p["diffuser_grid_m"])
            n_units = max(1, math.ceil(r.area_m2 / p["indoor_unit_area_m2"]))
            c = r.centroid or ((r.bounds[0] + r.bounds[2]) / 2, (r.bounds[1] + r.bounds[3]) / 2)
            item["diffusers"] = diff
            item["units"] = [c] if n_units == 1 else _cells_n(r, n_units)
            if not diff:
                warnings.append(f"{r.name} ({r.room_id}): irregular shape, no diffuser grid point fell inside; place manually.")
        if "fire" in services:
            pitch = _sprinkler_pitch(r, p)
            heads = _cells(r, pitch)
            item["sprinklers"] = heads
            item["sprinkler_pitch_m"] = round(pitch, 2)
            if not heads:
                warnings.append(f"{r.name} ({r.room_id}): irregular shape, no sprinkler grid point fell inside; place manually.")
        out["rooms"].append(item)
    return out


def _cells_n(room: PlanRoom, n: int) -> List[Tuple[float, float]]:
    minx, miny, maxx, maxy = room.bounds
    w, h = maxx - minx, maxy - miny
    cols = max(1, round(math.sqrt(n * w / h))) if h else n
    rows = max(1, math.ceil(n / cols))
    pts = []
    for i in range(cols):
        for j in range(rows):
            if len(pts) < n:
                pts.append((round(minx + (i + .5) * w / cols, 3), round(miny + (j + .5) * h / rows, 3)))
    return pts


def build_layout_dxf(model: PlanModel, *, services: Sequence[str] = ("hvac", "fire"), plant_xy: Optional[Tuple[float, float]] = None,
                     params: Optional[Dict[str, float]] = None, reference: str = "", project: str = "", revision: str = "A") -> LayoutResult:
    data = plan_layout(model, services=services, plant_xy=plant_xy, params=params)
    doc = _new_doc()
    for name, color in EXTRA.items():
        if name not in doc.layers:
            doc.layers.add(name, color=color)
    msp = doc.modelspace()
    K = 1000.0
    P = lambda pt: (pt[0] * K, pt[1] * K)
    for a, b in model.walls:
        msp.add_line(P(a), P(b), dxfattribs={"layer": "A-WALL"})
    by_id = {r.room_id: r for r in model.rooms}
    totals = {"diffusers": 0, "indoor_units": 0, "sprinklers": 0}
    plant = data["plant_xy"]
    msp.add_circle(P(plant), 300, dxfattribs={"layer": "M-UNIT"})
    msp.add_text("PLANT / RISER (confirm)", dxfattribs={"layer": "G-NOTE", "height": 250, "insert": (plant[0] * K + 400, plant[1] * K)})
    trunk_pts: List[Tuple[float, float]] = []
    for it in data["rooms"]:
        r = by_id[it["room_id"]]
        msp.add_lwpolyline([P(q) for q in r.polygon], close=True, dxfattribs={"layer": "A-ROOM"})
        c = r.centroid
        msp.add_text(f"{r.room_id} {r.name}  {r.area_m2:.1f} m2", dxfattribs={"layer": "G-NOTE", "height": 220, "insert": (r.bounds[0] * K + 150, r.bounds[1] * K + 150)})
        for d in it.get("diffusers", []):
            msp.add_circle(P(d), 150, dxfattribs={"layer": "M-DIFF"})
            totals["diffusers"] += 1
        for u in it.get("units", []):
            x, y = P(u)
            msp.add_lwpolyline([(x - 400, y - 400), (x + 400, y - 400), (x + 400, y + 400), (x - 400, y + 400)], close=True, dxfattribs={"layer": "M-UNIT"})
            totals["indoor_units"] += 1
        if it.get("units"):
            trunk_pts.append(it["units"][0])
        for h in it.get("sprinklers", []):
            x, y = P(h)
            msp.add_circle((x, y), 100, dxfattribs={"layer": "F-SPKL"})
            msp.add_line((x - 160, y), (x + 160, y), dxfattribs={"layer": "F-SPKL"})
            msp.add_line((x, y - 160), (x, y + 160), dxfattribs={"layer": "F-SPKL"})
            totals["sprinklers"] += 1
        if it.get("sprinklers"):
            rows: Dict[float, List[Tuple[float, float]]] = {}
            for h in it["sprinklers"]:
                rows.setdefault(h[1], []).append(h)
            ys = sorted(rows)
            for y in ys:
                xs = sorted(p[0] for p in rows[y])
                msp.add_line(P((xs[0], y)), P((xs[-1], y)), dxfattribs={"layer": "F-PIPE-BRANCH"}) if len(xs) > 1 else None
            first = rows[ys[0]]
            feed = (min(p[0] for p in first), ys[0])
            for seg in zip(_manhattan(plant, feed), _manhattan(plant, feed)[1:]):
                msp.add_line(P(seg[0]), P(seg[1]), dxfattribs={"layer": "F-PIPE-MAIN"})
            if len(ys) > 1:
                msp.add_line(P((feed[0], ys[0])), P((feed[0], ys[-1])), dxfattribs={"layer": "F-PIPE-MAIN"})
    if "hvac" in services:
        for t in trunk_pts:
            path = _manhattan(plant, t)
            for a, b in zip(path, path[1:]):
                msp.add_line(P(a), P(b), dxfattribs={"layer": "M-DUCT-TRUNK"})
    bx0, by0 = (model.bounds[0] if model.bounds else minx_of(model)) * K, (model.bounds[1] if model.bounds else miny_of(model)) * K
    ty = by0 - 4500
    lines = [f"CONCEPT LAYOUT - PRELIMINARY, NOT FOR CONSTRUCTION  |  Ref {reference}  Project {project}  Rev {revision}",
             "Equipment is placed on a rule grid; ducts and pipes are centre lines only. Not sized, not hydraulically checked, not clash checked.",
             f"Source plan: {model.source_file} ({model.method}). Rooms/scale must be confirmed by an engineer. Spacing rules: " +
             ", ".join(f"{k}={v:g}" for k, v in data["params"].items())]
    lines += data["warnings"]
    for i, s in enumerate(lines):
        msp.add_text(s, dxfattribs={"layer": "G-NOTE" if i else "G-TITLE", "height": 260, "insert": (bx0, ty - i * 450)})
    summary = {"services": list(services), "room_count": len(data["rooms"]), **totals, "params": data["params"], "plant_xy": plant,
               "rooms": [{k: (len(v) if isinstance(v, list) else v) for k, v in it.items()} for it in data["rooms"]]}
    return LayoutResult(dxf=_finish(doc), summary=summary, warnings=data["warnings"])


def minx_of(m: PlanModel) -> float:
    return min(r.bounds[0] for r in m.rooms if r.bounds)


def miny_of(m: PlanModel) -> float:
    return min(r.bounds[1] for r in m.rooms if r.bounds)
