"""Synthetic sample plans for tests and demos (no client data)."""
from __future__ import annotations

import io
from typing import List, Tuple

import ezdxf

ROOMS = [("OPEN OFFICE", 0, 0), ("MEETING ROOM", 8, 0), ("CABIN 1", 16, 0), ("CONFERENCE", 0, 8), ("SERVER ROOM", 8, 8), ("CABIN 2", 16, 8)]


def _wall_segments(door: float = 0.9) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    segs: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
    # outer shell
    segs += [((0, 0), (24, 0)), ((24, 0), (24, 14)), ((24, 14), (0, 14)), ((0, 14), (0, 0))]
    # room dividers (x = 8, 16) on both sides of the corridor
    for x in (8, 16):
        segs += [((x, 0), (x, 6)), ((x, 8), (x, 14))]
    # corridor walls y = 6 and y = 8 with a door gap at the middle of each room bay
    for y in (6, 8):
        for x0 in (0, 8, 16):
            mid = x0 + 4
            segs += [((x0, y), (mid - door / 2, y)), ((mid + door / 2, y), (x0 + 8, y))]
    return segs


def office_plan_dxf(*, units: str = "mm", with_labels: bool = True, room_outlines: bool = False) -> bytes:
    """24 m x 14 m office floor: 6 rooms of 8 x 6 m and a 24 x 2 m corridor, doors 0.9 m wide."""
    k = {"mm": 1000.0, "cm": 100.0, "m": 1.0}[units]
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = {"mm": 4, "cm": 5, "m": 6}[units]
    doc.layers.add("A-WALL"); doc.layers.add("A-ANNO-TEXT"); doc.layers.add("A-ROOM")
    msp = doc.modelspace()
    for (a, b) in _wall_segments():
        msp.add_line((a[0] * k, a[1] * k), (b[0] * k, b[1] * k), dxfattribs={"layer": "A-WALL"})
    if with_labels:
        for name, x, y in ROOMS:
            msp.add_text(name, dxfattribs={"layer": "A-ANNO-TEXT", "height": 0.3 * k, "insert": ((x + 4) * k, (y + 3) * k)})
        msp.add_text("CORRIDOR", dxfattribs={"layer": "A-ANNO-TEXT", "height": 0.3 * k, "insert": (12 * k, 7 * k)})
    if room_outlines:
        for name, x, y in ROOMS:
            msp.add_lwpolyline([(x * k, y * k), ((x + 8) * k, y * k), ((x + 8) * k, (y + 6) * k), (x * k, (y + 6) * k)], close=True, dxfattribs={"layer": "A-ROOM"})
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def office_plan_pdf(*, scale: int = 100, with_scale_text: bool = True) -> bytes:
    """Vector PDF of the same plan, drawn at 1:scale on an A3 sheet with the scale written on it."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A3, landscape
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A3))
    k = 1000.0 / scale * 72.0 / 25.4                # metres -> PDF points at 1:scale
    ox, oy = 60.0, 150.0
    c.setLineWidth(1.2)
    for (a, b) in _wall_segments():
        c.line(ox + a[0] * k, oy + a[1] * k, ox + b[0] * k, oy + b[1] * k)
    c.setFont("Helvetica", 9)
    for name, x, y in ROOMS:
        c.drawString(ox + (x + 3) * k, oy + (y + 3) * k, name)
    if with_scale_text:
        c.setFont("Helvetica", 10)
        c.drawString(60, 60, f"FIRST FLOOR PLAN   SCALE 1:{scale}")
    c.showPage(); c.save()
    return buf.getvalue()
