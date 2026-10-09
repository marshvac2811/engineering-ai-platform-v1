"""Governed standards scope references for engineering reports.

Scope references identify potentially relevant authoritative sections. They do
not create requirements and therefore cannot produce PASS/FAIL by themselves.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import yaml

_SCOPE_PATH = Path(__file__).resolve().parents[1] / "standards" / "scope_registry.yaml"


def load_scope_registry(path: str | Path = _SCOPE_PATH) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _source_map(registry: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {item["id"]: item for item in registry.get("sources", [])}


def scope_references_for_skill(skill_id: str) -> List[Dict[str, Any]]:
    """Return authoritative scope references relevant to a registered skill.

    The mapping is intentionally explicit so it can be audited and reviewed.
    """
    discipline_map = {
        "preliminary_load_estimation": ["hvac"],
        "duct_sizing": ["hvac"],
        "pump_head": ["hvac", "mechanical"],
        "hvac_fault_diagnosis": ["hvac"],
        "cooling_tower": ["hvac", "mechanical"],
        "refrigerant_pipe_sizing": ["hvac", "mechanical"],
        "vrf_sizing": ["hvac"],
        "cleanroom_ach": ["hvac"],
        "duct_leakage": ["hvac"],
        "chiller_selection_advisor": ["hvac"],
        "bms_points_generation": ["bms", "electrical"],
        "bms_controller_sizing": ["bms", "electrical"],
        "bms_cost_estimation": ["bms", "electrical"],
        "bms_alarm_evaluation": ["bms", "electrical"],
        "vfd_energy_savings": ["hvac", "electrical", "energy"],
        "vfd_derating": ["electrical", "hvac"],
        "harmonic_screening": ["electrical"],
        "hvac_decarbonisation": ["hvac", "energy", "sustainability"],
        "energy_payback": ["energy", "sustainability"],
        "hvac_design_package": ["hvac", "mechanical"],
        "hvac_boq": ["hvac", "mechanical", "construction"],
        "deviation_statement": ["construction", "project_management"],
        "facade_u_factor": ["facade", "construction", "energy"],
    }
    disciplines = discipline_map.get(skill_id, [])
    registry = load_scope_registry()
    result: List[Dict[str, Any]] = []
    for source in registry.get("sources", []):
        for ref in source.get("references", []):
            if set(ref.get("disciplines", [])) & set(disciplines):
                result.append({
                    "standard_id": source["id"],
                    "authority": source["authority"],
                    "code_name": source["name"],
                    "edition": source["edition"],
                    "reference_id": ref["ref_id"],
                    "reference": ref["reference"],
                    "title": ref["title"],
                    "reference_type": "SCOPE_REFERENCE",
                    "source_url": source["source_url"],
                })
    return result


def audit_scope_coverage(skill_ids: List[str]) -> Dict[str, Any]:
    covered = []
    uncovered = []
    for skill_id in skill_ids:
        if scope_references_for_skill(skill_id):
            covered.append(skill_id)
        else:
            uncovered.append(skill_id)
    return {
        "total_skills": len(skill_ids),
        "covered": covered,
        "uncovered": uncovered,
        "coverage_complete": not uncovered,
    }
