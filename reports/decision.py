from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from skill_registry.capabilities import get_capability, executable_skill_ids

# Explicit report names are part of the workflow contract. They deliberately
# describe registered engineering outputs rather than implying certification.
REPORT_TYPES = {
    "preliminary_load_estimation": "preliminary_load_estimation_report",
    "duct_sizing": "duct_sizing_report",
    "pump_head": "pump_head_calculation",
    "hvac_fault_diagnosis": "hvac_fault_diagnosis_report",
    "cooling_tower": "cooling_tower_sizing_report",
    "refrigerant_pipe_sizing": "refrigerant_pipe_sizing_report",
    "vrf_sizing": "vrf_sizing_report",
    "cleanroom_ach": "cleanroom_ach_report",
    "duct_leakage": "duct_leakage_report",
    "chiller_selection_advisor": "chiller_selection_advisory",
    "bms_points_generation": "bms_points_schedule",
    "bms_controller_sizing": "bms_controller_sizing_report",
    "bms_cost_estimation": "bms_cost_estimate",
    "bms_alarm_evaluation": "bms_alarm_evaluation_report",
    "vfd_energy_savings": "vfd_energy_savings_report",
    "vfd_derating": "vfd_derating_assessment",
    "harmonic_screening": "harmonic_screening_report",
    "hvac_decarbonisation": "hvac_decarbonisation_report",
    "energy_payback": "energy_payback_report",
    "hvac_boq": "hvac_bill_of_quantities",
    "deviation_statement": "technical_deviation_statement",
}

@dataclass(frozen=True)
class ReportProfile:
    skill_id: str
    report_type: str
    title: str
    deliverables: Tuple[str, ...]
    verified_check_ids: Tuple[str, ...]
    human_review_required: bool = True


def report_profile(skill_id: str) -> ReportProfile:
    capability = get_capability(skill_id)
    if capability is not None:
        report_type = REPORT_TYPES.get(skill_id, capability.report_type)
        title = capability.report_title or f"{capability.task} Report"
        return ReportProfile(
            skill_id=skill_id,
            report_type=report_type,
            title=title,
            deliverables=capability.deliverables,
            verified_check_ids=capability.verified_check_ids,
        )
    # Unknown/internal records get a safe generic profile; they are never
    # treated as an executable engineering capability.
    return ReportProfile(skill_id, "engineering_workflow_record", "Engineering Workflow Record", (), ())


def report_profiles() -> Dict[str, ReportProfile]:
    return {skill_id: report_profile(skill_id) for skill_id in executable_skill_ids()}
