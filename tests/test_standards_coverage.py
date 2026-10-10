from pathlib import Path

from code_engine.coverage import build_standards_applicability, standards_candidates
from skills.calculators.catalogue import CALCULATORS
from reports.adapter import build_report_envelope
from reports.profiles import registered_report_profiles
from skill_framework.registry import load_skill_registry

ROOT = Path(__file__).resolve().parents[1]


def test_every_executable_skill_has_a_standards_coverage_entry():
    registry = load_skill_registry(ROOT / "skill_registry" / "registry.yaml")
    profiles = registered_report_profiles()
    assert set(registry.executable_ids) == set(profiles)
    for skill_id in registry.executable_ids:
        assert skill_id in {"bms_cost_estimation", "deviation_statement", "fire_water_storage", "plumbing_water_demand"} or skill_id in {c.skill_id for c in CALCULATORS} or standards_candidates(skill_id)


def test_missing_context_blocks_claim_of_applicability():
    rows = build_standards_applicability("facade_u_factor", {})
    assert rows
    assert all(row["applicability_status"] == "CONTEXT_REQUIRED" for row in rows)


def test_report_envelope_exposes_standards_applicability_plan():
    report = build_report_envelope(
        skill_id="pump_head",
        result={"status": "draft_ready", "engineering_result": {"head_m": 42}},
        inputs={"flow_m3hr": 20},
        project_context={"jurisdiction": "India", "building_type": "commercial", "service_type": "chilled_water"},
    )
    assert report["standards_applicability"]
    assert all("applicability_status" in row for row in report["standards_applicability"])
