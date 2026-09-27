"""Authoritative report profiles for executable engineering skills.

Profiles describe presentation/deliverable boundaries only. They do not create
engineering calculations, code requirements, drawings, or BOQs that a skill
does not actually implement.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class ReportProfile:
    skill_id: str
    report_type: str
    title: str
    deliverables: Tuple[str, ...] = ("calculation_report",)


_PROFILES = {
    "preliminary_load_estimation": ("preliminary_load_estimation", "preliminary_load_estimation_report", "Preliminary Load Estimation Report", ("calculation_report",)),
    "duct_sizing": ("duct_sizing", "duct_sizing_report", "Duct Sizing Report", ("calculation_report",)),
    "pump_head": ("pump_head", "pump_head_calculation_report", "Pump Head Calculation Report", ("calculation_report",)),
    "hvac_fault_diagnosis": ("hvac_fault_diagnosis", "hvac_fault_diagnosis_report", "HVAC Fault Diagnosis Report", ("diagnostic_report",)),
    "cooling_tower": ("cooling_tower", "cooling_tower_sizing_report", "Cooling Tower Sizing Report", ("calculation_report",)),
    "refrigerant_pipe_sizing": ("refrigerant_pipe_sizing", "refrigerant_pipe_sizing_report", "Refrigerant Pipe Sizing Report", ("calculation_report",)),
    "vrf_sizing": ("vrf_sizing", "vrf_sizing_report", "VRF Sizing Report", ("calculation_report",)),
    "cleanroom_ach": ("cleanroom_ach", "cleanroom_ach_report", "Cleanroom ACH Report", ("calculation_report",)),
    "duct_leakage": ("duct_leakage", "duct_leakage_report", "Duct Leakage Report", ("assessment_report",)),
    "chiller_selection_advisor": ("chiller_selection_advisor", "chiller_selection_advisory", "Chiller Selection Advisory", ("advisory_report",)),
    "bms_points_generation": ("bms_points_generation", "bms_points_schedule", "BMS Points Schedule", ("schedule",)),
    "bms_controller_sizing": ("bms_controller_sizing", "bms_controller_sizing_report", "BMS Controller Sizing Report", ("calculation_report",)),
    "bms_cost_estimation": ("bms_cost_estimation", "bms_cost_estimate", "BMS Cost Estimate", ("cost_estimate",)),
    "bms_alarm_evaluation": ("bms_alarm_evaluation", "bms_alarm_evaluation_report", "BMS Alarm Evaluation Report", ("assessment_report",)),
    "vfd_energy_savings": ("vfd_energy_savings", "vfd_energy_savings_report", "VFD Energy Savings Report", ("calculation_report",)),
    "vfd_derating": ("vfd_derating", "vfd_derating_assessment", "VFD Derating Assessment", ("assessment_report",)),
    "harmonic_screening": ("harmonic_screening", "harmonic_screening_report", "Harmonic Screening Report", ("screening_report",)),
    "hvac_decarbonisation": ("hvac_decarbonisation", "hvac_decarbonisation_report", "HVAC Decarbonisation Report", ("scenario_report",)),
    "energy_payback": ("energy_payback", "energy_payback_report", "Energy Payback Report", ("financial_estimate",)),
    "hvac_boq": ("hvac_boq", "hvac_bill_of_quantities", "HVAC Bill of Quantities", ("boq",)),
    "deviation_statement": ("deviation_statement", "technical_deviation_statement", "Technical Deviation Statement", ("technical_statement",)),
    "facade_u_factor": ("facade_u_factor", "facade_thermal_performance", "Facade Thermal Performance Report", ("calculation_report", "compliance_assessment")),
}


def report_profile(skill_id: str) -> ReportProfile:
    """Return the explicit profile for an executable skill.

    Unknown skills intentionally receive no fabricated profile.
    """
    try:
        return ReportProfile(*_PROFILES[skill_id])
    except KeyError as exc:
        raise KeyError(f"No report profile registered for skill: {skill_id}") from exc


def registered_report_profiles() -> Dict[str, ReportProfile]:
    return {skill_id: report_profile(skill_id) for skill_id in sorted(_PROFILES)}
