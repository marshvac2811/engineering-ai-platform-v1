"""DXF schematic of an HVAC design package (rooms, loads, airflow, branch duct sizes, plant summary).

IMPORTANT: this is a SCHEMATIC, not a floor plan. Room positions are not known from any site or drawing, so
rooms are drawn as area-proportional boxes (assumed 3:2 aspect) in a grid. Only the numbers (area, load,
airflow, duct diameter, terminal class) come from the calculation; geometry is diagrammatic and is labelled
as such on the sheet. Output is deterministic (no clock, no randomness) so the same result gives the same file.
"""
from __future__ import annotations

import io
import math
import re
from typing import Any, Dict, List

import ezdxf
from ezdxf.enums import TextEntityAlignment

ASPECT = 1.5          # assumed width:depth of each schematic room box
GAP_MM = 3000.0
ROW_LIMIT_MM = 60000.0
TEXT_H = 350.0

LAYERS = {
    "A-ROOM": 7,           # white/black
    "A-ROOM-TEXT": 7,
    "M-DUCT-SCHEM": 5,     # blue
    "M-EQUIP-TEXT": 3,     # green
    "G-TITLE": 7,
    "G-NOTE": 1,           # red: preliminary / not-a-plan warnings
}


def _fmt(v: Any, nd: int = 0) -> str:
    try:
        return f"{float(v):,.{nd}f}"
    except (TypeError, ValueError):
        return str(v)


def build_design_schematic_dxf(result: Dict[str, Any], *, title: str = "HVAC Design Package - Schematic",
                               reference: str = "", project: str = "", revision: str = "A") -> bytes:
    rooms: List[Dict[str, Any]] = list(result.get("room_schedule") or [])
    if not rooms:
        raise ValueError("room_schedule is empty; nothing to draw")

    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    doc.header["$INSUNITS"] = 4
    # ezdxf stamps GUIDs and times into the header; pin them so identical results give identical bytes.
    for key, value in (("$FINGERPRINTGUID", "{00000000-0000-0000-0000-000000000000}"),
                       ("$VERSIONGUID", "{00000000-0000-0000-0000-000000000000}"),
                       ("$TDCREATE", 2451544.0), ("$TDUCREATE", 2451544.0),
                       ("$TDUPDATE", 2451544.0), ("$TDUUPDATE", 2451544.0)):
        if key in doc.header:
            doc.header[key] = value
    for name, color in LAYERS.items():
        doc.layers.add(name, color=color)
    msp = doc.modelspace()

    def text(s: str, x: float, y: float, layer: str, h: float = TEXT_H) -> None:
        t = msp.add_text(s, dxfattribs={"layer": layer, "height": h})
        t.set_placement((x, y), align=TextEntityAlignment.LEFT)

    # --- place room boxes in a wrapped grid, area-proportional ---
    x = y = row_h = 0.0
    top = 0.0
    placed = []
    for r in rooms:
        area_mm2 = max(float(r.get("area_m2") or 0.0), 1.0) * 1e6
        w = math.sqrt(area_mm2 * ASPECT)
        h = area_mm2 / w
        w, h = max(w, 6000.0), max(h, 4500.0)      # keep labels legible; positions are diagrammatic anyway
        if x > 0 and x + w > ROW_LIMIT_MM:
            x, y, row_h = 0.0, y - (row_h + GAP_MM + 4 * TEXT_H * 3), 0.0
        placed.append((r, x, y - h, w, h))
        msp.add_lwpolyline([(x, y - h), (x + w, y - h), (x + w, y), (x, y)], close=True, dxfattribs={"layer": "A-ROOM"})
        x += w + GAP_MM
        row_h = max(row_h, h)
    for r, rx, ry, w, h in placed:
        cx, top_y = rx + 400.0, ry + h - 700.0
        text(f"{r.get('room_id', '')}  {r.get('name', '')}", cx, top_y, "A-ROOM-TEXT", TEXT_H * 1.2)
        text(f"Area {_fmt(r.get('area_m2'), 1)} m2", cx, top_y - 650, "A-ROOM-TEXT")
        text(f"Load {_fmt(r.get('cooling_load_tr'), 2)} TR ({_fmt(r.get('cooling_load_kw'), 1)} kW)", cx, top_y - 1150, "M-EQUIP-TEXT")
        text(f"Supply {_fmt(r.get('supply_airflow_m3h'))} m3/h ({_fmt(r.get('supply_airflow_cfm'))} cfm)", cx, top_y - 1650, "M-EQUIP-TEXT")
        text(str(r.get("terminal_equipment", "")), cx, top_y - 2150, "M-EQUIP-TEXT", TEXT_H * 0.9)
        d = float(r.get("duct_diameter_mm") or 0)
        if d > 0:
            # duct drawn as a circle at its real diameter, so the sheet carries the sized dimension
            cr = d / 2.0
            ccx, ccy = rx + w - cr - 500.0, ry + cr + 500.0
            msp.add_circle((ccx, ccy), cr, dxfattribs={"layer": "M-DUCT-SCHEM"})
            text(f"D{_fmt(d)} @ {_fmt(r.get('duct_velocity_ms'), 2)} m/s", rx + 400.0, ry + 600.0, "M-DUCT-SCHEM")

    # --- plant summary and notes to the right of / below the grid ---
    min_x = 0.0
    min_y = min(p[2] for p in placed) - 9000.0
    ps = result.get("plant_summary") or {}
    lines = [
        f"BLOCK LOAD  {_fmt(result.get('block_load_tr'), 2)} TR  ({_fmt(result.get('block_load_kw'), 1)} kW)  after {_fmt(result.get('diversity_factor_pct'), 0)}% diversity",
        f"PLANT SUGGESTION  {result.get('plant_equipment_suggestion', '')}",
        f"TOTAL SUPPLY AIR  {_fmt(result.get('total_supply_airflow_m3h'))} m3/h   TOTAL AREA {_fmt(result.get('total_area_m2'), 1)} m2",
    ]
    if ps:
        lines.append(f"CHILLED WATER  {_fmt(ps.get('chilled_water_flow_m3h'), 1)} m3/h  header DN{_fmt(ps.get('chilled_water_header_dn'))}  "
                     f"{_fmt(ps.get('chilled_water_header_velocity_ms'), 2)} m/s   FAN MOTORS {_fmt(ps.get('total_fan_motor_kw'), 1)} kW")
    for k, ln in enumerate(lines):
        text(ln, min_x, min_y - k * 700.0, "M-EQUIP-TEXT")
    base = min_y - len(lines) * 700.0 - 1500.0
    notes = [
        "SCHEMATIC ONLY - NOT A FLOOR PLAN. Rooms are area-proportional boxes (3:2) in a grid; positions are not from the building.",
        "Numbers come from the preliminary calculation (rule-of-thumb loads, velocity-method branch ducts). Not for construction.",
        "Qualified engineer review required. Duct circles are drawn at the sized diameter (mm).",
    ]
    for k, ln in enumerate(notes):
        text(ln, min_x, base - k * 600.0, "G-NOTE", TEXT_H * 0.9)
    tb_y = base - len(notes) * 600.0 - 1500.0
    msp.add_lwpolyline([(0, tb_y), (60000, tb_y), (60000, tb_y - 3600), (0, tb_y - 3600)], close=True, dxfattribs={"layer": "G-TITLE"})
    text(title, 500, tb_y - 1200, "G-TITLE", TEXT_H * 1.6)
    text(f"Project: {project or '-'}    Reference: {reference or '-'}    Rev {revision}    Status: PRELIMINARY",
         500, tb_y - 2300, "G-TITLE")
    text(f"{result.get('building_type', '')} | {result.get('climate_zone', '')} | {result.get('room_count', len(rooms))} room(s)",
         500, tb_y - 3000, "G-TITLE")

    buf = io.StringIO()
    doc.write(buf)
    out = buf.getvalue()
    # ezdxf refreshes these header values at write time; normalise them so identical inputs give identical bytes.
    out = re.sub(r"(\$(?:VERSIONGUID|FINGERPRINTGUID)\n\s*2\n)\{[0-9A-Fa-f-]+\}", r"\g<1>{00000000-0000-0000-0000-000000000000}", out)
    out = re.sub(r"(\$(?:TDCREATE|TDUCREATE|TDUPDATE|TDUUPDATE)\n\s*40\n)[-0-9.eE+]+", r"\g<1>2451544.0", out)
    out = re.sub(r"(ezdxf|[0-9]+\.[0-9]+\.[0-9]+) @ [0-9T:.+-]+", r"\g<1> @ fixed", out)
    return out.encode("utf-8")
