"""Explicit calculation-to-layout routing.

A calculation result may drive a drawing object only when it identifies the
target room and the source calculation. No nearest-room/name/geometry inference
is performed.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List

from engineering.building.model import BuildingModel


_FIELD_BY_DISCIPLINE = {
    "HVAC": "airflow_m3h",
    "FIRE": ("protection_type", "total_storage_m3"),
    "PLUMBING": ("fixture_type", "design_demand_lpm"),
}


def route_calculation_outputs(
    building: BuildingModel,
    *,
    discipline: str,
    floor_id: str,
    calculation_outputs: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    discipline = str(discipline or "").upper()
    if discipline not in _FIELD_BY_DISCIPLINE:
        raise ValueError("discipline must be HVAC, FIRE or PLUMBING")
    floor = next((f for f in building.floors if f.floor_id == floor_id), None)
    if floor is None:
        raise ValueError(f"unknown floor_id: {floor_id}")

    rooms = {r.room_id: r for r in floor.rooms}
    room_inputs: Dict[str, Dict[str, Any]] = {}
    blockers: List[str] = []
    routed: List[Dict[str, Any]] = []
    fields = _FIELD_BY_DISCIPLINE[discipline]

    for output in calculation_outputs:
        if not isinstance(output, dict):
            blockers.append("Calculation output must be an object.")
            continue
        room_id = str(output.get("room_id") or "").strip()
        source_calculation = str(output.get("source_calculation") or "").strip()
        if not room_id:
            blockers.append("Calculation output is missing explicit room_id; placement was not inferred.")
            continue
        if room_id not in rooms:
            blockers.append(f"Calculation output targets unknown room_id: {room_id}")
            continue
        if not source_calculation:
            blockers.append(f"Calculation output for {room_id} is missing source_calculation.")
            continue
        if rooms[room_id].x_mm is None or rooms[room_id].y_mm is None:
            blockers.append(f"Room {room_id} has no explicit coordinates; placement was not inferred.")
            continue
        field = next((candidate for candidate in fields if output.get(candidate) is not None), None)
        if field is None:
            blockers.append(f"Calculation output for {room_id} is missing an explicit routed value.")
            continue
        room_inputs[room_id] = {field: output[field], "source_calculation": source_calculation}
        routed.append({"room_id": room_id, "source_calculation": source_calculation, "field": field})
    return {
        "status": "ready" if routed and not blockers else ("partial" if routed else "blocked"),
        "discipline": discipline,
        "floor_id": floor_id,
        "room_inputs": room_inputs,
        "routed": routed,
        "blockers": blockers,
        "human_review_required": True,
        "inference_performed": False,
    }
