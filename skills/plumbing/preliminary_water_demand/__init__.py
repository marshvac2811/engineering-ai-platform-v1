"""Governed preliminary plumbing water-demand calculator package."""
from __future__ import annotations

def calculate_plumbing_water_demand(*, fixtures: list[dict], diversity_factor_pct: float = 100.0):
    if not isinstance(fixtures, list) or not fixtures:
        raise ValueError("fixtures must be a non-empty list")
    if diversity_factor_pct <= 0 or diversity_factor_pct > 100:
        raise ValueError("diversity_factor_pct must be > 0 and <= 100")
    total_lpm = 0.0
    rows = []
    for item in fixtures:
        if not isinstance(item, dict):
            raise ValueError("each fixture must be an object")
        name = str(item.get("fixture_type") or "").strip()
        count = float(item.get("count") or 0)
        flow = float(item.get("flow_lpm") or 0)
        if not name or count <= 0 or flow <= 0:
            raise ValueError("each fixture requires fixture_type, positive count and positive flow_lpm")
        subtotal = count * flow
        total_lpm += subtotal
        rows.append({"fixture_type": name, "count": count, "flow_lpm": flow, "subtotal_lpm": subtotal})
    demand = total_lpm * diversity_factor_pct / 100.0
    return {
        "status": "preliminary",
        "fixture_rows": rows,
        "total_connected_flow_lpm": total_lpm,
        "diversity_factor_pct": diversity_factor_pct,
        "design_demand_lpm": demand,
        "design_demand_m3hr": demand * 0.06,
        "assumptions": ["Fixture flow rates and diversity factor are explicit project/governed inputs."],
        "limitations": ["Does not infer code fixture units, simultaneous-use rules, pipe sizes, pressure requirements, or statutory demand."],
        "human_review_required": True,
    }

__all__ = ["calculate_plumbing_water_demand"]
