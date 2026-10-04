"""Governed automatic input-assumption policy.

Only inputs explicitly registered here may be auto-filled. These are preliminary
engineering assumptions, not client facts and not universal code requirements.
Every applied assumption must be disclosed in the report and remains subject to
human review. Safety/regulatory-critical inputs should not be registered here.
"""
from __future__ import annotations
from typing import Any, Dict
from validators.governance import resolve_assumption

MAX_AUTO_ASSUMPTIONS_PER_TASK = 2

# skill_id -> input field -> governed assumption id
INPUT_ASSUMPTIONS: Dict[str, Dict[str, str]] = {
    "pump_head": {
        "material": "pump.pipe_material.preliminary_default",
        "margin_pct": "pump.design_margin.preliminary_default",
    },
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
