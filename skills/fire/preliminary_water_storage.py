"""Preliminary fire-water storage arithmetic from explicit project inputs.

No code/standard demand is invented here. Required flow and duration must be
provided or supplied by a separately governed source.
"""
from __future__ import annotations

def calculate_fire_water_storage(*, required_flow_lpm: float, duration_min: float, reserve_pct: float = 0.0):
    if required_flow_lpm <= 0 or duration_min <= 0 or reserve_pct < 0:
        raise ValueError("required_flow_lpm and duration_min must be positive; reserve_pct cannot be negative")
    base_l = required_flow_lpm * duration_min
    reserve_l = base_l * reserve_pct / 100.0
    return {
        "status": "preliminary",
        "required_flow_lpm": required_flow_lpm,
        "duration_min": duration_min,
        "base_storage_l": base_l,
        "reserve_l": reserve_l,
        "total_storage_l": base_l + reserve_l,
        "total_storage_m3": (base_l + reserve_l) / 1000.0,
        "assumptions": ["Required flow and duration are explicit project/governed inputs; no statutory demand was inferred."],
        "limitations": ["Does not select fire code demand, pump duty, sprinkler density, pipe diameter, or acceptance criteria."],
        "human_review_required": True,
    }
