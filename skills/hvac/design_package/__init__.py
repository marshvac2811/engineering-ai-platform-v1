"""HVAC design package (preliminary): per-room load, supply airflow, duct size and equipment schedule.

This composes existing governed calculators (preliminary load estimation, duct sizing). It adds no new
engineering formulas except unit conversion and the explicit airflow basis (CFM per TR), which is
always reported as an assumption for human review. Nothing is invented: rooms without an area are
rejected, and results are preliminary/budgetary only.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

from skills.hvac.duct_sizing import source_calculator as duct
from skills.hvac.preliminary_load_estimation import source_calculator as load

SQM_TO_SQFT = 10.7639
M3H_PER_CFM = 1.69901
KW_PER_TR = 3.5168525
DEFAULT_CFM_PER_TR = 400.0       # common rule-of-thumb; reported as an assumption, overridable
DEFAULT_VELOCITY_MS = 5.0        # main/branch comfort duct velocity; reported as an assumption, overridable
DEFAULT_MATERIAL = "gss"


def _terminal_class(tr: float) -> str:
    # Mirrors the source equipment bands of the load estimator, applied per room.
    if tr <= 5:
        return "Ductable / cassette split unit"
    if tr <= 20:
        return "Package unit or VRF indoor group"
    return "AHU / FCU bank on chilled water"


def design_package(*, building_type: str, climate_zone: str, rooms: List[Dict[str, Any]],
                   cfm_per_tr: float = DEFAULT_CFM_PER_TR, target_velocity_ms: float = DEFAULT_VELOCITY_MS,
                   diversity_factor_pct: float = 100.0, duct_material: str = DEFAULT_MATERIAL) -> Dict[str, Any]:
    if not rooms:
        raise ValueError("rooms must be a non-empty list")
    if cfm_per_tr <= 0 or target_velocity_ms <= 0:
        raise ValueError("cfm_per_tr and target_velocity_ms must be greater than zero")
    if not (0 < diversity_factor_pct <= 100):
        raise ValueError("diversity_factor_pct must be > 0 and <= 100")
    if duct_material not in duct.DUCT_MATERIALS:
        raise ValueError(f"Unknown duct material: {duct_material}")
    roughness = duct.DUCT_MATERIALS[duct_material]["roughness_mm"]

    seen = set()
    schedule: List[Dict[str, Any]] = []
    total_tr = 0.0
    total_area = 0.0
    for n, room in enumerate(rooms, 1):
        rid = str(room.get("room_id") or room.get("id") or f"R{n}")
        if rid in seen:
            raise ValueError(f"Duplicate room_id: {rid}")
        seen.add(rid)
        try:
            area_m2 = float(room["area_m2"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"Room {rid}: area_m2 is required and must be numeric")
        if area_m2 <= 0:
            raise ValueError(f"Room {rid}: area_m2 must be greater than zero")
        occ = room.get("occupancy")
        est = load.estimate_load(building_type, area_m2 * SQM_TO_SQFT, climate_zone, None if occ is None else int(occ))
        tr = float(est["total_tonnage_raw"])
        cfm = tr * cfm_per_tr
        flow_m3h = cfm * M3H_PER_CFM
        sized = duct.size_duct_velocity_method(flow_m3h, target_velocity_ms, roughness)
        schedule.append({
            "room_id": rid, "name": str(room.get("name") or rid), "area_m2": round(area_m2, 2),
            "cooling_load_tr": round(tr, 2), "cooling_load_kw": round(tr * KW_PER_TR, 2),
            "supply_airflow_cfm": round(cfm, 0), "supply_airflow_m3h": round(flow_m3h, 0),
            "duct_diameter_mm": sized["recommended_diameter_mm"], "duct_velocity_ms": sized["actual_velocity_ms"],
            "duct_friction_pa_per_m": sized["actual_friction_pa_per_m"], "terminal_equipment": _terminal_class(tr),
            "source_calculation": f"room:{rid}",
        })
        total_tr += tr
        total_area += area_m2

    block_tr = total_tr * diversity_factor_pct / 100.0
    plant = load._suggest_equipment(block_tr)
    return {
        "building_type": building_type, "climate_zone": climate_zone, "room_count": len(schedule),
        "total_area_m2": round(total_area, 2), "sum_of_room_loads_tr": round(total_tr, 2),
        "diversity_factor_pct": diversity_factor_pct, "block_load_tr": round(block_tr, 2),
        "block_load_kw": round(block_tr * KW_PER_TR, 2), "plant_equipment_suggestion": plant,
        "total_supply_airflow_m3h": round(sum(r["supply_airflow_m3h"] for r in schedule), 0),
        "room_schedule": schedule,
        "assumptions": [
            {"name": "cfm_per_tr", "value": cfm_per_tr, "basis": "Airflow per TR of sensible-plus-latent load; rule-of-thumb, replace with a psychrometric basis for detailed design."},
            {"name": "target_velocity_ms", "value": target_velocity_ms, "basis": "Duct velocity used for each room's supply branch."},
            {"name": "duct_material", "value": duct_material, "basis": f"Roughness {roughness} mm from the duct sizing source."},
            {"name": "diversity_factor_pct", "value": diversity_factor_pct, "basis": "100 means no diversity applied."},
        ],
        "limitations": [
            "Preliminary/budgetary rule-of-thumb loads; not a Manual J, CLTD or HAP calculation.",
            "Room loads use the building-type/climate benchmark per area; envelope, orientation, glazing and ventilation loads are not modelled.",
            "Equipment entries are classes, not selected models; final selection needs a qualified engineer and manufacturer data.",
            "Duct sizing is branch-level by velocity only; no network pressure balance or fittings loss is included.",
        ],
    }
