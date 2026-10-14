"""Concept-level HVAC and sprinkler layouts on a read plan, as an editable layered DXF (mm).

RULE-BASED AND PRELIMINARY. Equipment is positioned on a regular grid inside each room from stated spacing rules;
ducts and pipes are routed centre lines. Trunk ducts and sprinkler mains are given PRELIMINARY sizes (see sizing.py);
branches, fittings, equipment and hydraulics are NOT checked and nothing is clash-checked. Every spacing parameter is returned in the result so it can be shown, changed and approved.
Output is deterministic.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from shapely.geometry import Point, Polygon

from engineering.drawing.services_schematic import _finish, _new_doc
from engineering.layout.routing import build_grid, nearest_free, route_tree
from engineering.layout.sizing import size_ducts, size_sprinkler_mains
from engineering.plan.model import PlanModel, PlanRoom

DEFAULTS: Dict[str, float] = {
    "diffuser_grid_m": 3.0,          # max supply-diffuser spacing (typical comfort ceiling grid)
    "indoor_unit_area_m2": 40.0,     # one indoor unit / AHU terminal per this much floor area (concept)
    "sprinkler_max_spacing_m": 4.0,  # max spacing along and between branch lines
    "sprinkler_max_coverage_m2": 12.1,  # max floor area per head (light-hazard style; hazard class to be confirmed)
    "sprinkler_wall_max_m": 2.0,     # max distance from a wall
    "supply_air_m3h_per_m2": 20.0,   # concept supply air per floor area, used only to size the duct trunk
    "duct_max_velocity_ms": 6.0,     # trunk duct velocity limit for the preliminary size
}
EXTRA = {"M-DIFF": 3, "M-UNIT": 4, "M-DUCT-TRUNK": 5, "F-SPKL": 1, "F-PIPE-MAIN": 6, "F-PIPE-BRANCH": 2, "A-WALL": 8, "A-ROOM": 9, "G-SCHED": 7, "M-TAG": 3, "F-TAG": 2}


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
    grid = build_grid(model.walls, (minx, miny, maxx, maxy)) if model.walls else None
    if plant_xy is not None:
        plant = (float(plant_xy[0]), float(plant_xy[1]))
    else:
        corner = (minx + 1.0, miny + 1.0)
        c = nearest_free(grid, corner, limit=40) if grid is not None else None
        plant = grid.to_xy(c) if c is not None else corner
        warnings.append("Plant/riser position not given; a point near the lower-left corner inside the plan was used. Move it to the real plant room or shaft.")
    if grid is None:
        warnings.append("The plan has no wall lines (rooms came from drawn outlines), so duct and pipe runs are straight and may cross walls.")
    out: Dict[str, Any] = {"params": p, "plant_xy": plant, "rooms": [], "warnings": warnings, "_grid": grid}
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
    grid = data.pop("_grid", None)
    warnings: List[str] = data["warnings"]
    doc = _new_doc()
    for name, color in EXTRA.items():
        if name not in doc.layers:
            doc.layers.add(name, color=color)
    msp = doc.modelspace()
    K = 1000.0
    P = lambda pt: (pt[0] * K, pt[1] * K)
    for a_, b_ in model.walls:
        msp.add_line(P(a_), P(b_), dxfattribs={"layer": "A-WALL"})
    by_id = {r.room_id: r for r in model.rooms}
    totals = {"diffusers": 0, "indoor_units": 0, "sprinklers": 0}
    plant = data["plant_xy"]
    msp.add_circle(P(plant), 300, dxfattribs={"layer": "M-UNIT"})
    msp.add_text("PLANT / RISER (confirm)", dxfattribs={"layer": "G-NOTE", "height": 250, "insert": (plant[0] * K + 400, plant[1] * K)})
    unit_targets: List[Tuple[float, float]] = []
    unit_loads: List[float] = []
    fire_loads: List[float] = []
    fire_targets: List[Tuple[float, float]] = []
    schedule: List[Dict[str, Any]] = []
    unit_n = diff_n = spk_n = 0
    for it in data["rooms"]:
        r = by_id[it["room_id"]]
        msp.add_lwpolyline([P(q) for q in r.polygon], close=True, dxfattribs={"layer": "A-ROOM"})
        msp.add_text(f"{r.room_id} {r.name}  {r.area_m2:.1f} m2", dxfattribs={"layer": "G-NOTE", "height": 220, "insert": (r.bounds[0] * K + 150, r.bounds[1] * K + 150)})
        row = {"room_id": r.room_id, "room": r.name, "area_m2": r.area_m2}
        for d in it.get("diffusers", []):
            diff_n += 1
            msp.add_circle(P(d), 150, dxfattribs={"layer": "M-DIFF"})
            totals["diffusers"] += 1
        if it.get("diffusers"):
            row["diffusers"] = len(it["diffusers"])
        tags = []
        for u in it.get("units", []):
            unit_n += 1
            tag = f"FCU-{unit_n:02d}"
            tags.append(tag)
            x, y = P(u)
            msp.add_lwpolyline([(x - 400, y - 400), (x + 400, y - 400), (x + 400, y + 400), (x - 400, y + 400)], close=True, dxfattribs={"layer": "M-UNIT"})
            msp.add_text(tag, dxfattribs={"layer": "M-TAG", "height": 160, "insert": (x - 330, y - 60)})
            totals["indoor_units"] += 1
        if tags:
            row["indoor_units"] = ", ".join(tags)
            unit_targets.append(it["units"][0])
            unit_loads.append(r.area_m2 * data["params"]["supply_air_m3h_per_m2"])
        heads = it.get("sprinklers", [])
        for h in heads:
            spk_n += 1
            x, y = P(h)
            msp.add_circle((x, y), 100, dxfattribs={"layer": "F-SPKL"})
            msp.add_line((x - 160, y), (x + 160, y), dxfattribs={"layer": "F-SPKL"})
            msp.add_line((x, y - 160), (x, y + 160), dxfattribs={"layer": "F-SPKL"})
            totals["sprinklers"] += 1
        if heads:
            row["sprinklers"] = len(heads)
            rows_: Dict[float, List[Tuple[float, float]]] = {}
            for h in heads:
                rows_.setdefault(h[1], []).append(h)
            ys = sorted(rows_)
            for y in ys:
                xs = sorted(q[0] for q in rows_[y])
                if len(xs) > 1:
                    msp.add_line(P((xs[0], y)), P((xs[-1], y)), dxfattribs={"layer": "F-PIPE-BRANCH"})
            feed = (min(q[0] for q in rows_[ys[0]]), ys[0])
            if len(ys) > 1:
                msp.add_line(P((feed[0], ys[0])), P((feed[0], ys[-1])), dxfattribs={"layer": "F-PIPE-BRANCH"})
            fire_targets.append(feed)
            fire_loads.append(float(len(heads)))
        schedule.append(row)

    def draw_routes(targets, layer: str, what: str):
        if not targets:
            return []
        if grid is not None:
            res = route_tree(grid, plant, targets)
            segs, bad = res.segments, res.crossing_targets
            if bad:
                warnings.append(f"{what}: {len(bad)} run(s) found no open path through doors and are drawn straight; they may cross walls.")
        else:
            segs = []
            for t in targets:
                mid = (t[0], plant[1])
                segs += [(plant, mid), (mid, t)] if (t[0] != plant[0] and t[1] != plant[1]) else [(plant, t)]
        for a_, b_ in segs:
            if a_ != b_:
                msp.add_line(P(a_), P(b_), dxfattribs={"layer": layer})
        return segs

    def label_runs(runs, layer: str, text_fn) -> None:
        for run in runs:
            a_, b_ = run["a"], run["b"]
            if run["length_m"] < 2.5:
                continue
            mx, my = (a_[0] + b_[0]) / 2 * K, (a_[1] + b_[1]) / 2 * K
            vertical = abs(a_[0] - b_[0]) < 1e-6
            msp.add_text(text_fn(run), dxfattribs={"layer": "M-TAG" if layer.startswith("M") else "F-TAG", "height": 170,
                                                   "insert": (mx + (120 if vertical else -300), my + (-300 if vertical else 120)), "rotation": 90 if vertical else 0})

    sizing: Dict[str, Any] = {}
    if "hvac" in services:
        segs_d = draw_routes(unit_targets, "M-DUCT-TRUNK", "Duct trunk")
        if segs_d:
            sizing["duct_trunk"] = size_ducts(segs_d, plant, list(zip(unit_targets, unit_loads)), max_velocity_ms=data["params"]["duct_max_velocity_ms"])
            label_runs(sizing["duct_trunk"]["runs"], "M", lambda x: f"{x['size']} ({x['airflow_m3h']} m3/h)")
    if "fire" in services:
        segs_f = draw_routes(fire_targets, "F-PIPE-MAIN", "Sprinkler main")
        if segs_f:
            sizing["sprinkler_main"] = size_sprinkler_mains(segs_f, plant, list(zip(fire_targets, fire_loads)))
            label_runs(sizing["sprinkler_main"]["runs"], "F", lambda x: f"{x['size']} ({x['heads']} heads)")
            if any(x["note"] for x in sizing["sprinkler_main"]["runs"]):
                warnings.append("Sprinkler main: some runs exceed the pipe-schedule head limit; a hydraulic calculation is required.")

    bx0, by0 = (model.bounds[0] if model.bounds else minx_of(model)) * K, (model.bounds[1] if model.bounds else miny_of(model)) * K
    ty = by0 - 4500
    lines = [f"CONCEPT LAYOUT - PRELIMINARY, NOT FOR CONSTRUCTION  |  Ref {reference}  Project {project}  Rev {revision}",
             "Equipment is placed on a rule grid; ducts and pipes are centre lines routed through door openings. Trunk duct and sprinkler main sizes are preliminary (round duct by velocity; light-hazard pipe schedule); fittings, branches and hydraulics not checked, not clash checked.",
             f"Source plan: {model.source_file} ({model.method}). Rooms/scale must be confirmed by an engineer. Spacing rules: " +
             ", ".join(f"{k}={v:g}" for k, v in data["params"].items())]
    lines += warnings
    for i, s_ in enumerate(lines):
        msp.add_text(s_, dxfattribs={"layer": "G-NOTE" if i else "G-TITLE", "height": 260, "insert": (bx0, ty - i * 450)})
    # equipment schedule table
    sy = ty - (len(lines) + 1) * 450
    msp.add_text("EQUIPMENT SCHEDULE (concept quantities, not selected equipment)", dxfattribs={"layer": "G-SCHED", "height": 260, "insert": (bx0, sy)})
    for i, row in enumerate(schedule, 1):
        txt = f"{row['room_id']}  {row['room']}  {row['area_m2']:.1f} m2  |  indoor units: {row.get('indoor_units', '-')}  |  diffusers: {row.get('diffusers', '-')}  |  sprinklers: {row.get('sprinklers', '-')}"
        msp.add_text(txt, dxfattribs={"layer": "G-SCHED", "height": 220, "insert": (bx0, sy - i * 380)})
    summary = {"services": list(services), "room_count": len(data["rooms"]), **totals, "params": data["params"], "plant_xy": plant,
               "schedule": schedule, "sizing": {k: {"by_size": v["by_size"], **({"critical_loss_pa": v["critical_loss_pa"]} if "critical_loss_pa" in v else {}),
                                                    "runs": [{**{kk: vv for kk, vv in r_.items() if kk not in ("a", "b")}, "from": r_["a"], "to": r_["b"]} for r_ in v["runs"]]} for k, v in sizing.items()},
               "rooms": [{k: (len(v) if isinstance(v, list) else v) for k, v in it.items()} for it in data["rooms"]]}
    return LayoutResult(dxf=_finish(doc), summary=summary, warnings=warnings)


def minx_of(m: PlanModel) -> float:
    return min(r.bounds[0] for r in m.rooms if r.bounds)


def miny_of(m: PlanModel) -> float:
    return min(r.bounds[1] for r in m.rooms if r.bounds)
