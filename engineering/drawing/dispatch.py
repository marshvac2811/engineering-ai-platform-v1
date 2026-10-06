"""Controlled PDF/DXF drawing-package artifact generation.

This module converts the normalized drawing representation into deterministic,
review-gated deliverables. It does not claim construction/statutory approval.
"""
from __future__ import annotations

import io
import json
import zipfile
import hashlib
from typing import Any, Dict, Iterable

from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfgen import canvas


WATERMARK = "ENGINEERING AI PLATFORM • PRELIMINARY • CONTROLLED ISSUE"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _dxf_text(payload: Dict[str, Any]) -> str:
    lines = ["0", "SECTION", "2", "HEADER", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    for obj in payload.get("objects", []):
        kind = str(obj.get("kind") or "OBJECT")
        x = float(obj.get("x_mm") or 0)
        y = float(obj.get("y_mm") or 0)
        attrs = obj.get("attributes") or {}
        if isinstance(attrs, dict) and attrs.get("x2_mm") is not None and attrs.get("y2_mm") is not None:
            lines += ["0", "LINE", "8", str(payload.get("discipline") or "ENGINEERING"),
                      "10", f"{x:g}", "20", f"{y:g}", "30", "0",
                      "11", f"{float(attrs['x2_mm']):g}", "21", f"{float(attrs['y2_mm']):g}", "31", "0"]
        else:
            lines += ["0", "POINT", "8", str(payload.get("discipline") or "ENGINEERING"),
                      "10", f"{x:g}", "20", f"{y:g}", "30", "0"]
        label = f"{kind} {obj.get('object_id') or ''}".strip()
        lines += ["0", "TEXT", "8", str(payload.get("discipline") or "ENGINEERING"),
                  "10", f"{x + 8:g}", "20", f"{y + 8:g}", "30", "0",
                  "40", "2.5", "1", label[:120]]
    for ann in payload.get("annotations", []):
        lines += ["0", "TEXT", "8", "ANNOTATION", "10", f"{float(ann.get('x_mm') or 0):g}",
                  "20", f"{float(ann.get('y_mm') or 0):g}", "30", "0",
                  "40", "2.5", "1", str(ann.get("text") or "")[:160]]
    lines += ["0", "ENDSEC", "0", "EOF"]
    return "\n".join(lines) + "\n"


def build_drawing_dxf(payload: Dict[str, Any]) -> bytes:
    return _dxf_text(payload).encode("utf-8")


def build_drawing_pdf(*, manifest: Dict[str, Any], drawings: Iterable[Dict[str, Any]], watermark: str = WATERMARK) -> bytes:
    out = io.BytesIO()
    c = canvas.Canvas(out, pagesize=landscape(A3))
    width, height = landscape(A3)
    drawings = list(drawings)
    for index, drawing in enumerate(drawings, 1):
        c.setTitle(str(manifest.get("package_type") or "Engineering Drawing Package"))
        c.setFont("Helvetica-Bold", 14)
        c.drawString(30, height - 32, str(drawing.get("title") or drawing.get("drawing_id") or "Engineering Drawing"))
        c.setFont("Helvetica", 8)
        c.drawRightString(width - 30, height - 30,
                          f"{str(drawing.get('discipline') or '').upper()} | Floor {drawing.get('floor_id') or '-'} | Rev {drawing.get('revision') or '1'}")
        c.rect(25, 25, width - 50, height - 75)

        # Deterministic CAD-neutral preview: object positions are scaled into the page.
        objects = list(drawing.get("objects") or [])
        max_x = max([float(o.get("x_mm") or 0) for o in objects] + [1000.0])
        max_y = max([float(o.get("y_mm") or 0) for o in objects] + [700.0])
        scale = min((width - 100) / max_x, (height - 140) / max_y, 1.0)
        ox, oy = 45, 55
        for obj in objects:
            x = ox + float(obj.get("x_mm") or 0) * scale
            y = oy + float(obj.get("y_mm") or 0) * scale
            c.circle(x, y, 3, stroke=1, fill=0)
            c.setFont("Helvetica", 6)
            c.drawString(x + 5, y + 2, str(obj.get("kind") or obj.get("object_id") or "")[:28])
        for ann in drawing.get("annotations") or []:
            x = ox + float(ann.get("x_mm") or 0) * scale
            y = oy + float(ann.get("y_mm") or 0) * scale
            c.setFont("Helvetica", 7)
            c.drawString(x, y, str(ann.get("text") or "")[:90])

        c.setFont("Helvetica", 7)
        c.drawString(35, 12, "AI-assisted preliminary engineering drawing — qualified engineer review required.")
        c.drawRightString(width - 35, 12, watermark)
        c.showPage()
    if not drawings:
        c.setFont("Helvetica", 12)
        c.drawString(40, height - 50, "No drawing payloads supplied.")
        c.showPage()
    c.save()
    return out.getvalue()


def build_drawing_dispatch_package(*, manifest: Dict[str, Any], drawings: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    drawings = list(drawings)
    pdf = build_drawing_pdf(manifest=manifest, drawings=drawings)
    entries = {"drawing-package.pdf": pdf}
    for drawing in drawings:
        drawing_id = str(drawing.get("drawing_id") or "drawing")
        entries[f"{drawing_id}.dxf"] = build_drawing_dxf(drawing)
    entries["manifest.json"] = json.dumps(manifest, sort_keys=True, indent=2, default=str).encode("utf-8")

    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(entries.items()):
            archive.writestr(name, data)
    package = out.getvalue()
    return {
        "pdf": {"bytes": pdf, "sha256": sha256_bytes(pdf), "filename": "drawing-package.pdf"},
        "dxf_zip": {"bytes": package, "sha256": sha256_bytes(package), "filename": "drawing-package-dxf.zip"},
        "file_count": len(entries),
    }
