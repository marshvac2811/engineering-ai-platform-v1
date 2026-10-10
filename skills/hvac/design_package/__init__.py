"""HVAC design package (preliminary): per-room load, supply airflow, duct size and equipment schedule.

This composes existing governed calculators (preliminary load estimation, duct sizing). It adds no new
engineering formulas except unit conversion and the explicit airflow basis (CFM per TR), which is
always reported as an assumption for human review. Nothing is invented: rooms without an area are
rejected, and results are preliminary/budgetary only.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

from skills.calculators import formulas as F
from skills.hvac.duct_sizing import source_calculator as duct
from skills.hvac.preliminary_load_estimation import source_calculator as load

SQM_TO_SQFT = 10.7639
M3H_PER_CFM = 1.69901
KW_PER_TR = 3.5168525
DEFAULT_CFM_PER_TR = 400.0       # common rule-of-thumb; reported as an assumption, overridable
DEFAULT_VELOCITY_MS = 5.0        # main/branch comfort duct velocity; reported as an assumption, overridable
DEFAULT_MATERIAL = "gss"
DEFAULT_FAN_PRESSURE_PA = 500.0  # assumed total fan pressure per room unit; reported as an assumption
DEFAULT_CHW_DELTA_T = 5.5
# Generic nominal capacity series (TR) used only to round loads up to a commonly available size band.
# These are NOT vendor models; final selection needs manufacturer data.
_SPLIT_TR = (0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0)
_PACKAGE_TR = (7.5, 10.0, 12.5, 15.0, 17.5, 20.0)
_CHILLER_TR = (20, 30, 40, 50, 60, 80, 100, 120, 150, 200, 250, 300, 400, 500, 600, 800, 1000)


def _next_size(value: float, series) -> float | None:
    return next((x for x in series if x >= value - 1e-9), None)


_SPACE_TYPE_BY_BUILDING = {"office": "office", "retail": "retail", "hospital": "hospital_patient_room"}


def _terminal_class(tr: float) -> str:
    # Mirrors the source equipment bands of the load estimator, applied per room.
    if tr <= 5:
        return "Ductable / cassette split unit"
    if tr <= 20:
        return "Package unit or VRF indoor group"
    return "AHU / FCU bank on chilled water"


def design_package(*, building_type: str, climate_zone: str, rooms: List[Dict[str, Any]],
                   cfm_per_tr: float = DEFAULT_CFM_PER_TR, target_velocity_ms: float = DEFAULT_VELOCITY_MS,
                   diversity_factor_pct: float = 100.0, duct_material: str = DEFAULT_MATERIAL,
                   fan_pressure_pa: float = DEFAULT_FAN_PRESSURE_PA, chw_delta_t_c: float = DEFAULT_CHW_DELTA_T,
                   outdoor_db_c: float | None = None, outdoor_rh_pct: float | None = None,
                   room_db_c: float = 24.0, room_rh_pct: float = 50.0) -> Dict[str, Any]:
    if not rooms:
        raise ValueError("rooms must be a non-empty list")
    if cfm_per_tr <= 0 or target_velocity_ms <= 0:
        raise ValueError("cfm_per_tr and target_velocity_ms must be greater than zero")
    if not (0 < diversity_factor_pct <= 100):
        raise ValueError("diversity_factor_pct must be > 0 and <= 100")
    if duct_material not in duct.DUCT_MATERIALS:
        raise ValueError(f"Unknown duct material: {duct_material}")
    if fan_pressure_pa <= 0 or chw_delta_t_c <= 0:
        raise ValueError("fan_pressure_pa and chw_delta_t_c must be greater than zero")
    if (outdoor_db_c is None) != (outdoor_rh_pct is None):
        raise ValueError("Provide both outdoor_db_c and outdoor_rh_pct, or neither")
    roughness = duct.DUCT_MATERIALS[duct_material]["roughness_mm"]
    oa_h_diff = None
    if outdoor_db_c is not None:
        oa = F.moist_air_state(float(outdoor_db_c), float(outdoor_rh_pct))
        ra = F.moist_air_state(float(room_db_c), float(room_rh_pct))
        oa_h_diff = (oa["enthalpy_kj_kg"] - ra["enthalpy_kj_kg"], oa["density_kg_m3"])

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
        entry_extra: Dict[str, Any] = {}
        space_type = str(room.get("space_type") or _SPACE_TYPE_BY_BUILDING.get(building_type, "")).lower()
        if space_type in F.VENT_RATES:
            vent, _, _, _ = F.ventilation_rate({"floor_area_m2": area_m2, "occupants": float(occ or 0), "space_type": space_type})
            entry_extra["outdoor_air_l_s"] = vent["zone_outdoor_air_l_s"]
            entry_extra["outdoor_air_basis"] = f"ASHRAE 62.1 reference rates, space type '{space_type}'" + ("" if occ else "; occupancy not given so only the area component is counted")
            if oa_h_diff is not None:
                dh, rho = oa_h_diff
                entry_extra["ventilation_load_kw"] = round(max(0.0, vent["zone_outdoor_air_l_s"] / 1000.0 * rho * dh), 2)
        series = _SPLIT_TR if tr <= 5 else (_PACKAGE_TR if tr <= 20 else None)
        nominal = _next_size(tr, series) if series else None
        if nominal is not None:
            entry_extra["nominal_unit_size_tr"] = nominal
        fan, _, _, _ = F.fan_power({"airflow_m3h": flow_m3h, "total_static_pressure_pa": fan_pressure_pa})
        entry_extra["fan_motor_kw"] = fan["standard_motor_kw"]
        schedule.append({
            "room_id": rid, "name": str(room.get("name") or rid), "area_m2": round(area_m2, 2),
            "cooling_load_tr": round(tr, 2), "cooling_load_kw": round(tr * KW_PER_TR, 2),
            "supply_airflow_cfm": round(cfm, 0), "supply_airflow_m3h": round(flow_m3h, 0),
            "duct_diameter_mm": sized["recommended_diameter_mm"], "duct_velocity_ms": sized["actual_velocity_ms"],
            "duct_friction_pa_per_m": sized["actual_friction_pa_per_m"], "terminal_equipment": _terminal_class(tr),
            "source_calculation": f"room:{rid}", **entry_extra,
        })
        total_tr += tr
        total_area += area_m2

    block_tr = total_tr * diversity_factor_pct / 100.0
    plant = load._suggest_equipment(block_tr)
    chw_kw = block_tr * KW_PER_TR
    chw_flow = F.hydronic_flow({"load": chw_kw, "load_unit": "kw", "delta_t_c": chw_delta_t_c})[0]
    header, _, _, _ = F.water_pipe_sizing({"flow_m3h": chw_flow["flow_m3h"]})
    plant_summary = {
        "chilled_water_flow_m3h": chw_flow["flow_m3h"], "chilled_water_flow_usgpm": chw_flow["flow_usgpm"],
        "chilled_water_delta_t_c": chw_delta_t_c, "chilled_water_header_dn": header["selected_dn"],
        "chilled_water_header_velocity_ms": header["velocity_ms"],
        "chilled_water_header_friction_pa_per_m": header["friction_pa_per_m"],
        "total_fan_motor_kw": round(sum(r.get("fan_motor_kw") or 0 for r in schedule), 1),
    }
    plant_series = _CHILLER_TR if block_tr > 20 else (_PACKAGE_TR if block_tr > 5 else _SPLIT_TR)
    single = _next_size(block_tr, plant_series)
    half = _next_size(block_tr / 2.0, plant_series)
    plant_summary["plant_option_single_tr"] = single
    plant_summary["plant_option_two_equal_units_tr"] = half
    vent_rows = [r for r in schedule if "outdoor_air_l_s" in r]
    if vent_rows:
        plant_summary["total_outdoor_air_l_s"] = round(sum(r["outdoor_air_l_s"] for r in vent_rows), 2)
    if oa_h_diff is not None and vent_rows:
        plant_summary["total_ventilation_load_kw_not_included"] = round(sum(r.get("ventilation_load_kw", 0) for r in vent_rows), 2)
    return {
        "building_type": building_type, "climate_zone": climate_zone, "room_count": len(schedule),
        "total_area_m2": round(total_area, 2), "sum_of_room_loads_tr": round(total_tr, 2),
        "diversity_factor_pct": diversity_factor_pct, "block_load_tr": round(block_tr, 2),
        "block_load_kw": round(block_tr * KW_PER_TR, 2), "plant_equipment_suggestion": plant,
        "total_supply_airflow_m3h": round(sum(r["supply_airflow_m3h"] for r in schedule), 0),
        "room_schedule": schedule, "plant_summary": plant_summary,
        "assumptions": [
            {"name": "cfm_per_tr", "value": cfm_per_tr, "basis": "Airflow per TR of sensible-plus-latent load; rule-of-thumb, replace with a psychrometric basis for detailed design."},
            {"name": "target_velocity_ms", "value": target_velocity_ms, "basis": "Duct velocity used for each room's supply branch."},
            {"name": "duct_material", "value": duct_material, "basis": f"Roughness {roughness} mm from the duct sizing source."},
            {"name": "diversity_factor_pct", "value": diversity_factor_pct, "basis": "100 means no diversity applied."},
            {"name": "fan_pressure_pa", "value": fan_pressure_pa, "basis": "Assumed total fan pressure per room unit for motor sizing; replace with the real duct and coil pressure drop."},
            {"name": "chw_delta_t_c", "value": chw_delta_t_c, "basis": "Chilled-water temperature difference for header flow and pipe size (default 5.5 K)."},
        ],
        "limitations": [
            "Preliminary/budgetary rule-of-thumb loads; not a Manual J, CLTD or HAP calculation.",
            "Room loads use the building-type/climate benchmark per area; envelope, orientation and glazing are not modelled. Outdoor air is reported per ASHRAE 62.1 reference rates but its load is NOT added to the room loads (the benchmark may already include fresh air); the engineer must decide.",
            "Chilled-water header size covers the block load only; sub-mains, fittings and equipment pressure drops are not sized.",
            "Equipment entries are classes and generic nominal-capacity bands (split up to 5 TR, package up to 20 TR, chiller above 20 TR), not selected models; final selection needs a qualified engineer and manufacturer data. Plant options are a single unit or two equal units, each rounded up to the next nominal size; redundancy is not assumed.",
            "Duct sizing is branch-level by velocity only; no network pressure balance or fittings loss is included.",
        ],
    }
