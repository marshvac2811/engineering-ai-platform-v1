"""Conservative interpretation of extracted building-source evidence.

Only facts explicitly present in extracted text or deterministic DXF LINE
geometry are returned. No architectural semantics are inferred from geometry.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable

from engineering.building.schedule import extract_room_schedule


_ROOM_RE = re.compile(
    r"(?im)^\s*(?:room|space)\s*[:=-]\s*([^|,;\n]+)"
    r"(?:.*?\barea\s*[:=-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m2|m²|sqm))?"
)
_AREA_RE = re.compile(r"(?i)\barea\s*[:=-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m2|m²|sqm)\b")
_DIM_RE = re.compile(r"(?i)\b(?:width|w)\s*[:=-]\s*([0-9]+(?:\.[0-9]+)?)\s*mm\b.*?\b(?:height|h)\s*[:=-]\s*([0-9]+(?:\.[0-9]+)?)\s*mm\b")


def interpret_building_source(
    *,
    source_type: str,
    text: str = "",
    metadata: Dict[str, Any] | None = None,
    attachment_id: str | None = None,
    filename: str | None = None,
    line_geometry: Iterable[Dict[str, Any]] | None = None,
    candidate_rooms: Iterable[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    source_type = str(source_type or "").lower()
    metadata = dict(metadata or {})
    facts: Dict[str, Any] = {"rooms": [], "areas_m2": [], "dimensions_mm": []}
    warnings = []
    blockers = []

    if source_type in {"pdf", "docx", "text", "csv", "xlsx"}:
        for match in _ROOM_RE.finditer(text or ""):
            room_name = match.group(1).strip()
            area = float(match.group(2)) if match.group(2) else None
            facts["rooms"].append({"name": room_name, "area_m2": area, "source": {"attachment_id": attachment_id, "filename": filename}})
        known = {str(r["name"]).strip().lower() for r in facts["rooms"] if r.get("area_m2") is not None}
        for row in extract_room_schedule(text or "")["rooms"]:
            existing = next((r for r in facts["rooms"] if str(r["name"]).strip().lower() == row["name"].lower()), None)
            if existing is not None and row.get("occupancy") is not None and existing.get("occupancy") is None:
                existing["occupancy"] = row["occupancy"]
            if row["name"].lower() not in known:
                facts["rooms"].append({"name": row["name"], "area_m2": row["area_m2"], "occupancy": row.get("occupancy"),
                                       "source": {"attachment_id": attachment_id, "filename": filename}, "source_text": row["source_text"]})
        for match in _AREA_RE.finditer(text or ""):
            facts["areas_m2"].append(float(match.group(1)))
        for match in _DIM_RE.finditer(text or ""):
            facts["dimensions_mm"].append({"width_mm": float(match.group(1)), "height_mm": float(match.group(2))})
        if not facts["rooms"] and not facts["areas_m2"]:
            blockers.append("No explicit room/area facts were found in extracted source text.")
        if metadata.get("pages") and metadata.get("pages_with_text", metadata.get("pages")) == 0:
            blockers.append("Source appears image-only; OCR/visual semantic interpretation is not available in this V1 path.")
    elif source_type == "dxf":
        geometry = list(line_geometry or [])
        facts["line_geometry"] = geometry
        facts["supported_line_geometry_count"] = len(geometry)
        facts["semantic_interpretation"] = False
        warnings.append("DXF LINE geometry is registered, but architectural semantics (walls, rooms, doors and services) are not inferred from raw lines.")
        for c in candidate_rooms or []:
            facts["rooms"].append({"name": c["name"], "area_m2": c["area_m2"], "inferred": True, "review_required": True,
                                   "source": {"attachment_id": attachment_id, "filename": filename}, "basis": c.get("basis")})
        if facts["rooms"]:
            warnings.append("Rooms from DXF are candidates (closed polyline with one text label); confirm names and areas before use.")
        if not geometry:
            blockers.append("No supported DXF LINE geometry was extracted.")
    elif source_type == "cad_binary":
        blockers.append("Binary CAD geometry is not interpreted by this V1 source layer.")
    else:
        blockers.append(f"Unsupported building source type: {source_type or 'unknown'}")

    geometry_ready = bool(facts.get("line_geometry")) or any(
        r.get("area_m2") is not None and all(r.get(k) is not None for k in ("x_mm", "y_mm", "width_mm", "height_mm"))
        for r in facts["rooms"]
    )
    status = "partial" if facts["rooms"] or facts.get("line_geometry") else "blocked"
    design_rooms = []
    for n, r in enumerate((x for x in facts["rooms"] if x.get("area_m2")), 1):
        d = {"room_id": f"R{n}", "name": r["name"], "area_m2": r["area_m2"]}
        if r.get("occupancy") is not None:
            d["occupancy"] = r["occupancy"]
        design_rooms.append(d)
    return {
        "design_rooms": design_rooms,
        "design_rooms_need_confirmation": any(x.get("inferred") for x in facts["rooms"]),
        "status": status,
        "source_type": source_type,
        "attachment_id": attachment_id,
        "filename": filename,
        "facts": facts,
        "geometry_ready": geometry_ready,
        "semantic_interpretation": source_type != "dxf",
        "confidence": "explicit_source_facts_only",
        "human_review_required": True,
        "warnings": warnings,
        "blockers": blockers,
        "governance": "Source interpretation is preliminary and does not infer unsupported architectural semantics.",
    }
