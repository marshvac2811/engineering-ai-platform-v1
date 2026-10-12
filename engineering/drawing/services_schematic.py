"""Deterministic DXF block-diagram schematics for fire-water and domestic-water jobs.

These are SCHEMATICS, not piping layouts: boxes and arrows carry only numbers produced by the
preliminary calculations (storage, flow, pump duty, fixtures). No pipe routes or sizes are invented.
Output is deterministic (fixed header GUID/timestamps) so identical results give identical bytes.
"""
from __future__ import annotations

import io
import re
from typing import Any, Dict, List, Sequence, Tuple

import ezdxf
from ezdxf.enums import TextEntityAlignment

LAYERS = {"P-EQUIP": 3, "P-PIPE-SCHEM": 5, "P-TEXT": 7, "G-TITLE": 7, "G-NOTE": 1}
BOX_W, BOX_H, GAP, TEXT_H = 9000.0, 6000.0, 4500.0, 380.0


def _fmt(v: Any, nd: int = 0) -> str:
    try:
        return f"{float(v):,.{nd}f}"
    except (TypeError, ValueError):
        return "-" if v in (None, "") else str(v)


def _new_doc():
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    doc.header["$INSUNITS"] = 4
    for key, value in (("$FINGERPRINTGUID", "{00000000-0000-0000-0000-000000000000}"),
                       ("$VERSIONGUID", "{00000000-0000-0000-0000-000000000000}"),
                       ("$TDCREATE", 2451544.0), ("$TDUCREATE", 2451544.0),
                       ("$TDUPDATE", 2451544.0), ("$TDUUPDATE", 2451544.0)):
        if key in doc.header:
            doc.header[key] = value
    for name, color in LAYERS.items():
        doc.layers.add(name, color=color)
    return doc


def _finish(doc) -> bytes:
    buf = io.StringIO()
    doc.write(buf)
    out = buf.getvalue()
    out = re.sub(r"(\$(?:VERSIONGUID|FINGERPRINTGUID)\n\s*2\n)\{[0-9A-Fa-f-]+\}", r"\g<1>{00000000-0000-0000-0000-000000000000}", out)
    out = re.sub(r"(\$(?:TDCREATE|TDUCREATE|TDUPDATE|TDUUPDATE)\n\s*40\n)[-0-9.eE+]+", r"\g<1>2451544.0", out)
    out = re.sub(r"(ezdxf|[0-9]+\.[0-9]+\.[0-9]+) @ [0-9T:.+-]+", r"\g<1> @ fixed", out)
    return out.encode("utf-8")


def _draw(title: str, boxes: Sequence[Tuple[str, Sequence[str]]], notes: Sequence[str], *, reference: str, project: str,
          revision: str, subtitle: str) -> bytes:
    doc = _new_doc()
    msp = doc.modelspace()

    def text(s: str, x: float, y: float, layer: str, h: float = TEXT_H) -> None:
        t = msp.add_text(s, dxfattribs={"layer": layer, "height": h})
        t.set_placement((x, y), align=TextEntityAlignment.LEFT)

    x = 0.0
    prev_right = None
    for head, lines in boxes:
        msp.add_lwpolyline([(x, 0), (x + BOX_W, 0), (x + BOX_W, BOX_H), (x, BOX_H)], close=True, dxfattribs={"layer": "P-EQUIP"})
        text(head, x + 400, BOX_H - 900, "P-TEXT", TEXT_H * 1.25)
        for k, ln in enumerate(lines):
            text(ln, x + 400, BOX_H - 1700 - k * 650, "P-TEXT")
        if prev_right is not None:
            ymid = BOX_H / 2
            msp.add_line((prev_right, ymid), (x, ymid), dxfattribs={"layer": "P-PIPE-SCHEM"})
            msp.add_lwpolyline([(x - 700, ymid + 350), (x, ymid), (x - 700, ymid - 350)], dxfattribs={"layer": "P-PIPE-SCHEM"})
        prev_right = x + BOX_W
        x += BOX_W + GAP
    base = -2500.0
    for k, ln in enumerate(notes):
        text(ln, 0, base - k * 600.0, "G-NOTE", TEXT_H * 0.9)
    tb_y = base - len(notes) * 600.0 - 1500.0
    width = max(x - GAP, 40000.0)
    msp.add_lwpolyline([(0, tb_y), (width, tb_y), (width, tb_y - 3600), (0, tb_y - 3600)], close=True, dxfattribs={"layer": "G-TITLE"})
    text(title, 500, tb_y - 1200, "G-TITLE", TEXT_H * 1.6)
    text(f"Project: {project or '-'}    Reference: {reference or '-'}    Rev {revision}    Status: PRELIMINARY", 500, tb_y - 2300, "G-TITLE")
    text(subtitle, 500, tb_y - 3000, "G-TITLE")
    return _finish(doc)


_COMMON_NOTES = (
    "SCHEMATIC ONLY - NOT A PIPING LAYOUT. Boxes and arrows show the sequence of equipment, not routes, levels or pipe sizes.",
    "Numbers come from the preliminary calculation. Not for construction. Qualified engineer review required.",
)


def build_fire_schematic_dxf(results: Dict[str, Any], *, reference: str = "", project: str = "", revision: str = "A") -> bytes:
    """results: merged engineering_result keys of sprinkler_demand and/or fire_water_storage."""
    if not any(results.get(k) is not None for k in ("total_storage_m3", "water_volume_m3", "total_demand_l_min", "sprinkler_demand_l_min")):
        raise ValueError("no fire-water results to draw")
    storage = results.get("total_storage_m3", results.get("water_volume_m3"))
    flow = results.get("total_demand_l_min", results.get("required_flow_lpm"))
    boxes: List[Tuple[str, List[str]]] = [
        ("FIRE WATER TANK", [f"Storage {_fmt(storage, 1)} m3", f"Duration {_fmt(results.get('duration_min'))} min",
                              f"Reserve {_fmt(results.get('reserve_l'))} L" if results.get("reserve_l") is not None else "Reserve not stated"]),
        ("FIRE PUMP", [f"Duty flow {_fmt(flow)} L/min", "Pump head and selection", "not determined here"]),
        ("SPRINKLER SYSTEM", [f"Hazard {results.get('hazard_class', '-')}", f"Density {_fmt(results.get('design_density_l_min_m2'), 1)} L/min/m2",
                              f"Design area {_fmt(results.get('design_area_m2'))} m2", f"Sprinkler {_fmt(results.get('sprinkler_demand_l_min'))} L/min"]),
        ("HOSE / HYDRANT", [f"Allowance {_fmt(results.get('hose_allowance_l_min'))} L/min", f"Total demand {_fmt(flow)} L/min"]),
    ]
    return _draw("Fire Water Schematic", boxes, _COMMON_NOTES + ("Fire code demand, pump selection and pipe sizing are not determined here.",),
                 reference=reference, project=project, revision=revision, subtitle="Fire water storage, pump and demand")


def build_water_schematic_dxf(results: Dict[str, Any], *, reference: str = "", project: str = "", revision: str = "A") -> bytes:
    """results: merged engineering_result keys of domestic_water_tank_sizing and/or plumbing water demand."""
    if not any(results.get(k) is not None for k in ("underground_tank_l", "overhead_tank_l", "design_demand_lpm", "fixture_rows")):
        raise ValueError("no domestic-water results to draw")
    fixtures = [f"{r.get('fixture_type', '')} x{_fmt(r.get('count'))} @ {_fmt(r.get('flow_lpm'), 1)} L/min" for r in (results.get("fixture_rows") or [])][:6]
    boxes: List[Tuple[str, List[str]]] = [
        ("UNDERGROUND TANK", [f"Capacity {_fmt(results.get('underground_tank_l'))} L", f"Daily demand {_fmt(results.get('daily_demand_l'))} L"]),
        ("TRANSFER PUMP", [f"Design demand {_fmt(results.get('design_demand_m3hr'), 2)} m3/h" if results.get("design_demand_m3hr") is not None else "Duty flow not stated",
                           "Pump head and selection", "not determined here"]),
        ("OVERHEAD TANK", [f"Capacity {_fmt(results.get('overhead_tank_l'))} L"]),
        ("FIXTURES", fixtures or [f"Design demand {_fmt(results.get('design_demand_lpm'))} L/min"]),
    ]
    return _draw("Domestic Water Schematic", boxes, _COMMON_NOTES + ("Fire reserve, flushing/HVAC make-up and pipe sizing are not included.",),
                 reference=reference, project=project, revision=revision, subtitle="Domestic water storage, transfer and fixtures")
