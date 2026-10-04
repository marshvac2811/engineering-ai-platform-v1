from __future__ import annotations

from pathlib import Path

import pytest

from skills.common import SkillRequest
from orchestrator.engine import execute, registered_skills


ROOT = Path(__file__).resolve().parents[1]


# One governed, deterministic baseline input set per executable skill.
# chiller_efficiency is intentionally excluded because the registry marks it
# source_audit_pending and therefore non-executable.
BASELINE_CASES = {
    "preliminary_load_estimation": {
        "building_type": "office",
        "area_sqft": 5500,
        "climate_zone": "composite",
        "occupancy": 60,
    },
    "duct_sizing": {
        "airflow": 1800,
        "airflow_unit": "m3/hr",
        "method": "velocity",
        "duct_type": "round",
        "target_velocity_ms": 5,
    },
    "pump_head": {
        "flow_m3hr": 30,
        "diameter_mm": 100,
        "straight_length_m": 80,
        "static_head_m": 20,
        "margin_pct": 10,
        "roughness_mm": 0.15,
    },
    "hvac_fault_diagnosis": {
        "rule_id": "pump_cavitation",
        "values": {
            "high_vibration": "yes",
            "noise": "yes",
            "low_suction_pressure": "yes",
        },
    },
    "cooling_tower": {
        "load_method": "chiller",
        "chiller_tr": 200,
        "chiller_cop": 5,
        "range_c": 5.5,
        "wet_bulb_c": 28,
        "approach_c": 4.5,
        "coc": 4,
        "drift_pct": 0.02,
    },
    "refrigerant_pipe_sizing": {
        "refrigerant": "R410A",
        "capacity_kw": 14,
        "suction_velocity": 10,
        "liquid_velocity": 1.2,
        "suction_length": 25,
        "liquid_length": 25,
    },
    "vrf_sizing": {
        "zones": [
            {"name": "A", "area": 40, "load_factor": 130},
            {"name": "B", "area": 120, "load_factor": 150},
        ],
        "combination_ratio": 120,
        "total_pipe_length_m": 100,
        "farthest_branch_length_m": 40,
        "odu_idu_height_diff_m": 20,
        "idu_idu_height_diff_m": 8,
    },
    "cleanroom_ach": {
        "room_type": "Operating Room",
        "length_m": 7,
        "width_m": 6,
        "height_m": 3.2,
    },
    "duct_leakage": {
        "sections": [{"width_mm": 600, "height_mm": 400, "length_m": 20}],
        "test_pressure_pa": 1000,
        "measured_leakage_ls": 20,
        "target_class": 6,
    },
    "chiller_selection_advisor": {
        "total_load_tr": 300,
        "efficiency_kw_per_tr": 0.7,
        "annual_hours": 3000,
        "load_factor_pct": 70,
        "tariff_per_kwh": 8.5,
        "duty_modules": 2,
        "redundancy_level": 1,
        "water_available": "yes",
        "space_available": "ample",
        "efficiency_priority": "high",
    },
    "bms_points_generation": {
        "equipment_counts": {"ahu": 2, "pump": 1},
        "points_per_controller": 32,
        "controllers_per_panel": 4,
    },
    "bms_controller_sizing": {
        "total_points": 96,
        "points_per_controller": 32,
        "controllers_per_panel": 4,
    },
    "bms_cost_estimation": {
        "ahu_count": 2,
        "chiller_count": 1,
        "pump_count": 2,
        "vfd_count": 2,
        "misc_points": 4,
        "points_per_controller": 32,
        "controllers_per_panel": 4,
        "cost_per_point": 100,
        "cost_per_controller": 20000,
        "cost_per_panel": 15000,
        "bms_software_cost": 50000,
        "engineering_pct": 10,
    },
    "bms_alarm_evaluation": {
        "point_type": "analog",
        "point_id": "AHU1_SAT",
        "value": 20,
    },
    "vfd_energy_savings": {
        "motor_kw": 22,
        "speed_reduction_pct": 20,
        "static_head_fraction": 20,
        "annual_hours": 4000,
        "tariff_per_kwh": 9,
    },
    "vfd_derating": {
        "motor_kw": 15,
        "ambient_temp_c": 50,
        "altitude_m": 1200,
    },
    "harmonic_screening": {
        "total_vfd_kva": 200,
        "transformer_kva": 800,
    },
    "hvac_decarbonisation": {
        "annual_energy_kwh": 100000,
        "tariff": 10,
        "efficiency_gain_pct": 10,
        "om_program_cost": 100000,
        "capacity_tr": 100,
        "replacement_cost": 5000000,
        "life_extension_years": 3,
    },
    "energy_payback": {
        "capacity_old": 200,
        "efficiency_old": 0.8,
        "capacity_new": 180,
        "efficiency_new": 0.6,
        "annual_hours": 3000,
        "load_factor_pct": 70,
        "tariff_per_kwh": 8.5,
        "investment": 2000000,
        "incremental_om": 50000,
        "project_life_years": 10,
    },
    "hvac_boq": {
        "categories": [
            {
                "name": "Duct",
                "items": [
                    {"description": "GI duct", "unit": "kg", "qty": 100, "rate": 200}
                ],
            }
        ],
        "contingency_pct": 5,
        "overhead_pct": 10,
        "tax_pct": 18,
    },
    "deviation_statement": {
        "rows": [
            {"clause": "A", "specified": "100", "offered": "100", "status": "comply", "remarks": ""},
            {"clause": "B", "specified": "200", "offered": "180", "status": "deviate", "remarks": "Alternative"},
            {"clause": "C", "specified": "-", "offered": "-", "status": "na", "remarks": ""},
        ]
    },
    "facade_u_factor": {
        "components": [
            {"name": "glass", "area_m2": 60, "u_factor": 2.4},
            {"name": "frame", "area_m2": 20, "u_factor": 2.8},
            {"name": "opaque", "area_m2": 20, "u_factor": 0.6},
        ]
    },
}


def req(skill_id: str, inputs: dict, *, project_context: dict | None = None):
    return SkillRequest(
        skill_id=skill_id,
        inputs=inputs,
        project_context=project_context or {},
    )


@pytest.mark.parametrize("skill_id", sorted(BASELINE_CASES))
def test_at_01_to_at_23_executable_skill_baselines(skill_id):
    result = execute(req(skill_id, BASELINE_CASES[skill_id]))
    assert result.status in {"draft_ready", "completed"}, (
        f"{skill_id} failed baseline trial: {result.to_dict()}"
    )
    assert result.engineering_result, f"{skill_id} returned no engineering result"
    assert result.human_review_required is True


def test_at_23_facade_u_factor_ecbc_path():
    result = execute(
        req(
            "facade_u_factor",
            BASELINE_CASES["facade_u_factor"],
            project_context={
                "building_type": "commercial",
                "component": "vertical_fenestration",
            },
        )
    )
    assert result.status == "completed"
    assert result.engineering_result["overall_u_factor_w_m2k"] == pytest.approx(1.98)
    assert result.source_revision == "phase5-facade-u-factor-1"
    assert result.human_review_required is True


def test_at_11_chiller_efficiency_remains_blocked():
    result = execute(req("chiller_efficiency", {}))
    assert result.status == "skill_not_registered"


def test_at_24_missing_required_input_is_requested():
    result = execute(
        req(
            "duct_sizing",
            {
                "method": "velocity",
                "duct_type": "round",
                "target_velocity_ms": 5,
            },
        )
    )
    assert result.status == "input_validation_failed"
    assert any("airflow" in e.lower() for e in result.validation_errors)


def test_at_25_invalid_input_is_rejected():
    result = execute(
        req(
            "duct_sizing",
            {
                "airflow": -100,
                "airflow_unit": "m3/hr",
                "method": "velocity",
                "duct_type": "round",
                "target_velocity_ms": 5,
            },
        )
    )
    assert result.status == "input_validation_failed"
    assert result.validation_errors


def test_at_27_conditional_input_is_enforced():
    result = execute(
        req(
            "cooling_tower",
            {
                "load_method": "chiller",
                "range_c": 5,
                "wet_bulb_c": 28,
                "approach_c": 4,
                "coc": 4,
                "drift_pct": 0.02,
            },
        )
    )
    assert result.status == "input_validation_failed"
    assert any("chiller" in e.lower() for e in result.validation_errors)


def test_at_38_unsupported_compliance_boundary_is_explicit():
    result = execute(
        req(
            "facade_u_factor",
            BASELINE_CASES["facade_u_factor"],
            project_context={"building_type": "residential", "component": "unknown"},
        )
    )
    assert result.status == "completed"
    warnings = " ".join(result.warnings).lower()
    assert "preliminary" in warnings
    assert "certified" in warnings


def test_at_39_skill_metadata_traceability():
    result = execute(req("duct_sizing", BASELINE_CASES["duct_sizing"]))
    payload = result.to_dict()
    assert payload.get("source_revision")
    assert payload.get("human_review_required") is True


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "trial_id,relative_path,required_terms",
    [
        ("AT-29", "reports/evidence.py", ["sha256", "evidence"]),
        ("AT-30", "jobs/service.py", ["dispatch", "approval"]),
        ("AT-32", "jobs/service.py", ["rework"]),
        ("AT-33", "jobs/service.py", ["approval_invalidated", "rework_parent_revision"]),
        ("AT-34", "reports/service.py", ["supersedes_report_id", "revision"]),
        ("AT-35", "reports/register.py", ["evidence", "Evidence Register"]),
        ("AT-36", "reports/register.py", ["revision_history", "Revision History"]),
        ("AT-37", "reports/artifacts.py", ["Skill version", "Source revision"]),
        ("AT-39", "reports/adapter.py", ["skill_version", "source_revision"]),
        ("AT-40", "api/app.py", ["/v1/intake"]),
    ],
)
def test_governance_contracts_present(trial_id, relative_path, required_terms):
    source = _read(relative_path)
    lowered = source.lower()
    missing = [term for term in required_terms if term.lower() not in lowered]
    assert not missing, f"{trial_id}: missing contract terms {missing} in {relative_path}"


def test_at_28_multi_input_execution_plan_contract():
    source = _read("orchestrator/executor.py")
    for term in ("depends_on", "input_bindings", "task_outputs", "execution_trace"):
        assert term in source


def test_at_41_external_intake_is_not_falsely_marked_as_engineering_core():
    matrix = _read("acceptance/ACCEPTANCE_MATRIX.md")
    assert "AT-41" in matrix
    assert "real or approved normalized external event" in matrix


def test_at_42_final_gate_requires_zero_unexplained_failures():
    matrix = _read("acceptance/ACCEPTANCE_MATRIX.md")
    assert "AT-42" in matrix
    assert "No unexplained failure remains" in matrix


def test_acceptance_registry_scope():
    assert len(registered_skills()) == 22
    assert "facade_u_factor" in registered_skills()
    assert "chiller_efficiency" not in registered_skills()
