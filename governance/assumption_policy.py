"""Governed automatic input-assumption policy.

Only inputs explicitly registered here may be auto-filled. These are preliminary
engineering assumptions, not client facts and not universal code requirements.
Every applied assumption must be disclosed in the report and remains subject to
human review. Safety/regulatory-critical inputs should not be registered here.
"""
from __future__ import annotations
from typing import Any, Dict
from validators.governance import resolve_assumption

MAX_AUTO_ASSUMPTIONS_PER_TASK = 4

# skill_id -> input field -> governed assumption id
INPUT_ASSUMPTIONS: Dict[str, Dict[str, str]] = {
    "pump_head": {
        "material": "pump.pipe_material.preliminary_default",
        "margin_pct": "pump.design_margin.preliminary_default",
    },
    "duct_sizing": {
        "method": "duct.method.preliminary_default",
        "duct_type": "duct.shape.preliminary_default",
        "target_velocity_ms": "duct.target_velocity.preliminary_default",
    },
    "preliminary_load_estimation": {
        "climate_zone": "load.climate_zone.preliminary_default",
    },
    "fan_power_sizing": {
        "total_static_pressure_pa": "fan.total_static_pressure.preliminary_default",
    },
    "refrigerant_pipe_sizing": {
        "suction_velocity": "refrigerant.suction_velocity.preliminary_default",
        "liquid_velocity": "refrigerant.liquid_velocity.preliminary_default",
    },
    "cooling_tower": {
        "range_c": "tower.range.preliminary_default",
        "approach_c": "tower.approach.preliminary_default",
        "coc": "tower.coc.preliminary_default",
        "drift_pct": "tower.drift.preliminary_default",
    },
    "vrf_sizing": {"combination_ratio": "vrf.combination_ratio.preliminary_default"},
    "cooling_coil_load": {
        "leaving_db_c": "coil.leaving_db.preliminary_default",
        "leaving_rh_pct": "coil.leaving_rh.preliminary_default",
    },
    "heat_recovery_assessment": {
        "effectiveness_pct": "heat_recovery.effectiveness.preliminary_default",
        "exhaust_db_c": "heat_recovery.exhaust_db.preliminary_default",
        "exhaust_rh_pct": "heat_recovery.exhaust_rh.preliminary_default",
    },
    "vfd_derating": {
        "ambient_temp_c": "vfd_derating.ambient.preliminary_default",
        "altitude_m": "vfd_derating.altitude.preliminary_default",
    },
    "hvac_design_package": {"climate_zone": "design.climate_zone.preliminary_default"},
}

# Assumptions that only make sense for certain already-resolved inputs.
_APPLIES_WHEN = {
    ("duct_sizing", "target_velocity_ms"): lambda r: r.get("method") == "velocity",
}


def resolve_input_assumptions(
    skill_id: str,
    inputs: Dict[str, Any],
    assumptions_context: Dict[str, Any] | None = None,
) -> tuple[Dict[str, Any], list[Dict[str, Any]], list[str]]:
    resolved = dict(inputs or {})
    applied: list[Dict[str, Any]] = []
    blockers: list[str] = []
    context = dict(assumptions_context or {})
    for field, assumption_id in INPUT_ASSUMPTIONS.get(skill_id, {}).items():
        applies = _APPLIES_WHEN.get((skill_id, field))
        if applies and not applies(resolved):
            continue
        value = resolved.get(field)
        if value is not None and not (isinstance(value, str) and not value.strip()):
            continue
        assumption = resolve_assumption(assumption_id, override_context=context)
        if "value" not in assumption:
            blockers.append(f"{skill_id}.{field}: registered assumption {assumption_id} has no usable value")
            continue
        if len(applied) >= MAX_AUTO_ASSUMPTIONS_PER_TASK:
            blockers.append(f"{skill_id}: automatic assumption limit ({MAX_AUTO_ASSUMPTIONS_PER_TASK}) exceeded")
            break
        resolved[field] = assumption["value"]
        applied.append({
            **assumption,
            "parameter": field,
            "status": "ASSUMED_DUE_TO_CLIENT_DATA_UNAVAILABLE",
            "client_confirmation": "recommended",
        })
    return resolved, applied, blockers
