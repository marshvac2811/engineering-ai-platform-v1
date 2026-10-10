"""Universal standards coverage and applicability planning.

This module deliberately does not invent engineering requirements. It maps an
executable skill to standards that may be relevant and identifies what must be
known before a compliance check can be treated as applicable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class StandardsCandidate:
    standard_id: str
    reason: str
    applicability_fields: Tuple[str, ...]
    compliance_ready: bool = False


# Candidate standards are references, not automatic compliance requirements.
# A requirement is compliance-ready only when a governed, structured
# requirement exists in standards/registry.yaml and applicability is established.
_COVERAGE: Dict[str, Tuple[StandardsCandidate, ...]] = {
    "preliminary_load_estimation": (
        StandardsCandidate("bis_nbc_2016", "Building services / HVAC reference for building design.", ("jurisdiction", "building_type", "occupancy")),
        StandardsCandidate("ashrae_55_2023", "Thermal comfort reference when the project requires it.", ("climate", "occupancy", "comfort_criteria")),
    ),
    "duct_sizing": (
        StandardsCandidate("bis_nbc_2016", "HVAC building-services reference.", ("jurisdiction", "building_type", "occupancy")),
        StandardsCandidate("ashrae_62_1_2025", "Ventilation-system reference where applicable.", ("occupancy", "ventilation_standard")),
    ),
    "pump_head": (
        StandardsCandidate("bis_nbc_2016", "Building-services reference when the pump serves a covered building service.", ("jurisdiction", "building_type", "service_type")),
    ),
    "hvac_fault_diagnosis": (
        StandardsCandidate("bis_nbc_2016", "Building-services reference for HVAC systems.", ("jurisdiction", "building_type", "service_type")),
    ),
    "cooling_tower": (
        StandardsCandidate("bis_nbc_2016", "Mechanical/building-services reference.", ("jurisdiction", "building_type", "service_type")),
        StandardsCandidate("ashrae_90_1_2025", "Energy-performance reference where contract/jurisdiction requires it.", ("jurisdiction", "contractual_standard")),
    ),
    "refrigerant_pipe_sizing": (
        StandardsCandidate("bis_nbc_2016", "HVAC building-services reference.", ("jurisdiction", "building_type", "system_type")),
    ),
    "vrf_sizing": (
        StandardsCandidate("bis_nbc_2016", "HVAC building-services reference.", ("jurisdiction", "building_type", "system_type")),
        StandardsCandidate("ashrae_90_1_2025", "Energy-performance reference where applicable.", ("jurisdiction", "contractual_standard")),
    ),
    "cleanroom_ach": (
        StandardsCandidate("bis_nbc_2016", "Building-services reference; specialist cleanroom requirements may also apply.", ("jurisdiction", "facility_type", "cleanroom_class")),
    ),
    "duct_leakage": (
        StandardsCandidate("bis_nbc_2016", "HVAC installation/building-services reference.", ("jurisdiction", "building_type")),
    ),
    "chiller_selection_advisor": (
        StandardsCandidate("bis_nbc_2016", "HVAC building-services reference.", ("jurisdiction", "building_type")),
        StandardsCandidate("ashrae_90_1_2025", "Energy-performance reference where applicable.", ("jurisdiction", "contractual_standard")),
    ),
    "bms_points_generation": (
        StandardsCandidate("bis_nbc_2016", "Building automation/system-services reference.", ("jurisdiction", "building_type", "automation_scope")),
    ),
    "bms_controller_sizing": (
        StandardsCandidate("bis_nbc_2016", "Building automation/system-services reference.", ("jurisdiction", "building_type", "automation_scope")),
    ),
    "bms_cost_estimation": (),
    # Input-governed preliminary calculators: no statutory demand, density or fixture-unit rules are
    # implemented, so no standards candidate is asserted until a source/audit basis is established.
    "hvac_design_package": (
        StandardsCandidate("bee_ecbc_2017", "Energy-code context for commercial HVAC design where applicable.", ("jurisdiction", "building_type")),
        StandardsCandidate("ashrae_90_1_2025", "Energy-performance reference where applicable.", ("jurisdiction", "contractual_standard")),
    ),
    "fire_water_storage": (),
    "plumbing_water_demand": (),
    "psychrometric_properties": (),
    "cooling_coil_load": (),
    "ventilation_rate": (),
    "fan_power_sizing": (),
    "water_pipe_sizing": (),
    "expansion_tank_sizing": (),
    "hydronic_flow_rate": (),
    "heat_recovery_assessment": (),
    "chiller_iplv": (),
    "duct_pressure_drop": (),
    "insulation_condensation": (),
    "cable_voltage_drop": (),
    "sprinkler_demand": (),
    "hot_water_heater_sizing": (),
    "rainwater_drainage": (),
    "solar_pv_sizing": (),
    "carbon_emissions": (),
    "bms_alarm_evaluation": (
        StandardsCandidate("bis_nbc_2016", "Building automation/system-services reference.", ("jurisdiction", "building_type", "automation_scope")),
    ),
    "vfd_energy_savings": (
        StandardsCandidate("ashrae_90_1_2025", "Energy-performance reference where applicable.", ("jurisdiction", "contractual_standard")),
        StandardsCandidate("bis_nbc_2016", "Building-services reference where the VFD serves building systems.", ("jurisdiction", "building_type", "service_type")),
    ),
    "vfd_derating": (
        StandardsCandidate("bis_nbc_2016", "Electrical/building-services context where applicable.", ("jurisdiction", "building_type", "service_type")),
    ),
    "harmonic_screening": (
        StandardsCandidate("bis_nbc_2016", "Electrical/allied-installation context where applicable.", ("jurisdiction", "building_type", "electrical_scope")),
    ),
    "hvac_decarbonisation": (
        StandardsCandidate("ashrae_90_1_2025", "Energy-performance reference where applicable.", ("jurisdiction", "contractual_standard")),
        StandardsCandidate("bee_ecbc_2017", "Commercial building energy-code reference where applicable.", ("jurisdiction", "building_type", "connected_load_kw")),
    ),
    "energy_payback": (
        StandardsCandidate("bee_ecbc_2017", "Commercial-building energy context where applicable.", ("jurisdiction", "building_type", "connected_load_kw")),
    ),
    "hvac_boq": (
        StandardsCandidate("bis_nbc_2016", "Building-services scope reference; BOQ quantities remain project-specific.", ("jurisdiction", "building_type")),
    ),
    "deviation_statement": (),
    "energy_optimisation_study": (),
    "boq_takeoff": (),
    "facade_u_factor": (
        StandardsCandidate("bis_nbc_2016", "NBC Part 6 Section 8 covers glass and glazing.", ("jurisdiction", "building_type", "component")),
        StandardsCandidate("bee_ecbc_2017", "Commercial building-envelope energy reference where applicable.", ("jurisdiction", "building_type", "component", "connected_load_kw")),
        StandardsCandidate("ashrae_90_1_2025", "Building-envelope energy reference where contract/jurisdiction requires it.", ("jurisdiction", "contractual_standard", "climate")),
    ),
}


def standards_candidates(skill_id: str) -> Tuple[StandardsCandidate, ...]:
    """Return governed candidate references for a registered skill."""
    return _COVERAGE.get(skill_id, ())


def build_standards_applicability(skill_id: str, project_context: Dict[str, object] | None = None):
    """Return an auditable applicability plan without asserting compliance."""
    context = project_context or {}
    rows = []
    for candidate in standards_candidates(skill_id):
        missing = [field for field in candidate.applicability_fields if not context.get(field)]
        rows.append({
            "standard_id": candidate.standard_id,
            "reason": candidate.reason,
            "applicability_fields": list(candidate.applicability_fields),
            "missing_context": missing,
            "applicability_status": "READY_FOR_CHECK" if not missing else "CONTEXT_REQUIRED",
            "compliance_ready": candidate.compliance_ready,
        })
    return rows
