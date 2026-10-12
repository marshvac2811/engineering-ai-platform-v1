"""File readers. Each returns a PlanReadResult; unsupported inputs say exactly why and what to send instead."""
from __future__ import annotations

import io
import math
import os
import re
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from engineering.plan.geometry import assign_labels, rooms_from_walls, to_plan_rooms
from engineering.plan.model import PlanModel, PlanReadResult, PlanRoom

_INSUNITS_TO_M = {1: 0.0254, 2: 0.3048, 4: 0.001, 5: 0.01, 6: 1.0, 7: 1000.0, 3: 1609.344, 8: 2.54e-8, 9: 2.54e-5, 10: 0.9144}
_UNIT_NAMES = {1: "inches", 2: "feet", 4: "millimetres", 5: "centimetres", 6: "metres", 10: "yards"}
_ROOM_LAYER = re.compile(r"(room|space|area|zone|rm)", re.I)
_WALL_LAYER = re.compile(r"(wall|a-wall|partition|walls)", re.I)
_SKIP_LAYER = re.compile(r"(dim|text|anno|hatch|furn|equip|grid|defpoints|tile|door|window|glaz)", re.I)


def read_plan(filename: str, data: bytes, *, units: Optional[str] = None, scale: Optional[float] = None) -> PlanReadResult:
    """Dispatch on file type. `units` in {mm,cm,m,in,ft} overrides DXF units; `scale` is the drawing scale denominator for PDFs (100 for 1:100)."""
    ext = os.path.splitext(filename or "")[1].lower()
    try:
        if ext == ".dxf":
            return _read_dxf(filename, data, units=units)
        if ext == ".dwg":
            return _read_dwg(filename, data, units=units)
        if ext == ".pdf":
            from engineering.plan.pdf_reader import read_pdf_plan
            return read_pdf_plan(filename, data, scale=scale)
        if ext in {".csv", ".txt", ".xlsx", ".xls", ".xlsm"}:
            return _read_schedule(filename, data)
        if ext in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
            return PlanReadResult("unsupported", None, [
                "Photos and scans of drawings need an image-reading service, which is not enabled on this server yet.",
                "Please send the plan as DXF or PDF exported from CAD, or an Excel/CSV room schedule."])
    except Exception as exc:  # never crash intake on a bad file
        return PlanReadResult("failed", None, [f"Could not read {filename}: {type(exc).__name__}: {exc}"])
    return PlanReadResult("unsupported", None, [f"File type '{ext or 'unknown'}' is not supported. Send DXF, PDF, or an Excel/CSV room schedule."])


# --------------------------------------------------------------------------- DXF
def _units_factor(doc, override: Optional[str], extents_hint: float) -> Tuple[float, str, List[str]]:
    warns: List[str] = []
    ov = {"mm": (0.001, "millimetres"), "cm": (0.01, "centimetres"), "m": (1.0, "metres"), "in": (0.0254, "inches"), "ft": (0.3048, "feet")}
    if override:
        f, n = ov[override.lower()]
        return f, f"{n} (stated by user)", warns
    code = int(doc.header.get("$INSUNITS", 0) or 0)
    if code in _INSUNITS_TO_M and code in _UNIT_NAMES:
        return _INSUNITS_TO_M[code], _UNIT_NAMES[code], warns
    # unitless: guess from the extents of the drawing (typical building plan 10-200 m)
    if extents_hint > 2000:
        f, n = 0.001, "millimetres"
    elif extents_hint > 300:
        f, n = 0.01, "centimetres"
    else:
        f, n = 1.0, "metres"
    warns.append(f"The DXF does not declare its units; assumed {n} from the drawing size. Please confirm.")
    return f, f"{n} (assumed)", warns


def _poly_points(e) -> List[Tuple[float, float]]:
    t = e.dxftype()
    if t == "LWPOLYLINE":
        return [(p[0], p[1]) for p in e.get_points("xy")]
    if t == "POLYLINE":
        return [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
    return []


def _read_dxf(filename: str, data: bytes, *, units: Optional[str]) -> PlanReadResult:
    import ezdxf
    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as fh:
        fh.write(data)
        path = fh.name
    try:
        try:
            doc = ezdxf.readfile(path)
        except Exception as exc:
            return PlanReadResult("failed", None, [f"The DXF could not be opened: {exc}"])
    finally:
        os.unlink(path)
    msp = doc.modelspace()
    segs: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
    wall_segs: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
    room_polys: List[List[Tuple[float, float]]] = []
    labels: List[Tuple[str, Tuple[float, float]]] = []
    xs: List[float] = []
    ys: List[float] = []

    def add_seg(a, b, layer):
        segs.append((a, b))
        if _WALL_LAYER.search(layer):
            wall_segs.append((a, b))
        xs.extend([a[0], b[0]]); ys.extend([a[1], b[1]])

    for e in msp:
        t = e.dxftype()
        layer = str(getattr(e.dxf, "layer", "0"))
        if t == "LINE":
            if not _SKIP_LAYER.search(layer):
                add_seg((e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y), layer)
        elif t in {"LWPOLYLINE", "POLYLINE"}:
            pts = _poly_points(e)
            closed = bool(getattr(e, "is_closed", False) or getattr(e, "closed", False))
            if len(pts) >= 3 and closed and _ROOM_LAYER.search(layer) and not _SKIP_LAYER.search(layer):
                room_polys.append(pts)
            elif not _SKIP_LAYER.search(layer):
                ring = pts + ([pts[0]] if closed and pts else [])
                for a, b in zip(ring, ring[1:]):
                    add_seg(a, b, layer)
        elif t == "TEXT":
            labels.append((str(e.dxf.text), (e.dxf.insert.x, e.dxf.insert.y)))
        elif t == "MTEXT":
            labels.append((re.sub(r"\\[A-Za-z][^;]*;|[{}]", "", e.text).split("\\P")[0].strip(), (e.dxf.insert.x, e.dxf.insert.y)))
    if not (segs or room_polys):
        return PlanReadResult("failed", None, ["No drawable geometry found in the DXF (no lines or polylines on usable layers)."])
    allx = xs + [p[0] for poly in room_polys for p in poly]
    ally = ys + [p[1] for poly in room_polys for p in poly]
    extent = max(max(allx) - min(allx), max(ally) - min(ally))
    factor, unit_note, warns = _units_factor(doc, units, extent)

    def m(pt):  # to metres
        return (pt[0] * factor, pt[1] * factor)

    model = PlanModel(source_file=filename, file_type="dxf", units_note=unit_note, scale_note="model space, 1:1 (no scaling needed)")
    model.warnings.extend(warns)
    label_m = [(t, m(p)) for t, p in labels]

    from shapely.geometry import Polygon
    if room_polys:
        polys = [Polygon([m(p) for p in poly]) for poly in room_polys]
        polys = [p if p.is_valid else p.buffer(0) for p in polys]
        polys = [p for p in polys if not p.is_empty and p.area >= 1.0]
        names = assign_labels(polys, label_m)
        model.rooms = to_plan_rooms(polys, names, confidence="high")
        model.method = "closed room/space outlines on room layers"
        model.needs_confirmation = False if all(r.name_source == "label" for r in model.rooms) else True
        if model.needs_confirmation:
            model.warnings.append("Some rooms have no text label inside them and were named 'Space n'. Please confirm room names.")
        model.walls = [(m(a), m(b)) for a, b in (wall_segs or [])]
    else:
        use = wall_segs or segs
        if not wall_segs:
            model.warnings.append("No wall layer was found; all line work was used to detect rooms. Results may include furniture or fixtures.")
        wall_m = [(m(a), m(b)) for a, b in use]
        polys = rooms_from_walls(wall_m)
        if not polys:
            return PlanReadResult("failed", None, ["Could not find closed rooms in the wall lines. Check that walls are drawn as continuous lines (door gaps up to about 1 m are closed automatically)."])
        names = assign_labels(polys, label_m)
        model.rooms = to_plan_rooms(polys, names, confidence="medium")
        model.walls = wall_m
        model.method = "rooms detected from wall line work (door gaps up to ~1.1 m bridged)"
        model.warnings.append("Rooms were detected from wall lines, not from drawn room outlines. Please check the count and areas.")
        model.needs_confirmation = True
    bx = [p[0] for r in model.rooms for p in r.polygon]
    by = [p[1] for r in model.rooms for p in r.polygon]
    model.bounds = (min(bx), min(by), max(bx), max(by))
    return PlanReadResult("ok" if not model.needs_confirmation else "partial", model, list(model.warnings))


# --------------------------------------------------------------------------- DWG
def _read_dwg(filename: str, data: bytes, *, units: Optional[str]) -> PlanReadResult:
    conv = shutil.which("dwg2dxf")
    if not conv:
        return PlanReadResult("unsupported", None, [
            "DWG files need a converter that is not installed on this server yet.",
            "For now please export the drawing as DXF (in AutoCAD: SAVEAS, choose DXF) or as PDF, and send that.",
            "The converter (LibreDWG) can be enabled by moving the server to a Docker deployment."])
    with tempfile.TemporaryDirectory() as d:
        src, out = os.path.join(d, "in.dwg"), os.path.join(d, "out.dxf")
        with open(src, "wb") as fh:
            fh.write(data)
        proc = subprocess.run([conv, "-y", "-o", out, src], capture_output=True, timeout=120)
        if not os.path.exists(out):
            return PlanReadResult("failed", None, ["The DWG could not be converted: " + (proc.stderr.decode("utf-8", "ignore")[:200] or "unknown error")])
        with open(out, "rb") as fh:
            res = _read_dxf(filename, fh.read(), units=units)
    if res.model:
        res.model.file_type = "dwg (converted to dxf)"
        res.model.warnings.append("DWG was converted automatically; please check units and room areas.")
        res.model.needs_confirmation = True
    return res


# --------------------------------------------------------------------------- schedules (no geometry)
def _read_schedule(filename: str, data: bytes) -> PlanReadResult:
    from engineering.building.schedule import extract_room_schedule
    ext = os.path.splitext(filename)[1].lower()
    if ext in {".xlsx", ".xlsm", ".xls"}:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
        lines: List[str] = []
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                cells = [str(c).strip() for c in row if c not in (None, "")]
                if cells:
                    lines.append(" | ".join(cells))
        text = "\n".join(lines)
    else:
        text = data.decode("utf-8-sig", errors="replace")
    found = extract_room_schedule(text)
    if not found["rooms"]:
        return PlanReadResult("failed", None, ["No rooms with an area and unit (m2 or sq ft) were found in this file."] + list(found.get("skipped") or [])[:5])
    model = PlanModel(source_file=filename, file_type=ext.lstrip("."), has_geometry=False, method="room schedule (no geometry)",
                      units_note="areas as stated", scale_note="n/a")
    for r in found["rooms"]:
        model.rooms.append(PlanRoom(room_id=str(r.get("room_id") or f"R{len(model.rooms)+1:02d}"), name=str(r.get("name") or "Space"), polygon=[],
                                    area_m2=float(r["area_m2"]), occupancy=r.get("occupancy"), name_source="schedule", confidence="high"))
    model.warnings.append("This file has areas but no geometry, so only schematic drawings (not floor-plan layouts) can be produced.")
    model.needs_confirmation = False
    return PlanReadResult("ok", model, list(model.warnings))
