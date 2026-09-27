from pathlib import Path

from reports.adapter import build_report_envelope
from reports.profiles import registered_report_profiles, report_profile
from skill_framework.registry import load_skill_registry

ROOT = Path(__file__).resolve().parents[1]


def test_every_executable_skill_has_an_explicit_report_profile():
    registry = load_skill_registry(ROOT / "skill_registry" / "registry.yaml")
    profiles = registered_report_profiles()
    assert set(registry.executable_ids) == set(profiles)


def test_pending_skill_has_no_report_profile():
    registry = load_skill_registry(ROOT / "skill_registry" / "registry.yaml")
    assert "chiller_efficiency" in registry.pending_ids
    try:
        report_profile("chiller_efficiency")
    except KeyError:
        pass
    else:
        raise AssertionError("pending skill must not receive an executable report profile")


def test_report_envelope_preserves_engineering_result_and_trace():
    payload = build_report_envelope(
        skill_id="pump_head",
        result={
            "status": "draft_ready",
            "engineering_result": {"head_m": 42.1},
            "calculation_trace": [{"step": "friction"}],
            "assumptions": [{"name": "margin", "value": 10}],
            "warnings": ["preliminary"],
            "human_review_required": True,
        },
        inputs={"flow_m3hr": 20},
        project_context={"location": "Delhi"},
    )
    assert payload["report_type"] == "pump_head_calculation_report"
    assert payload["engineering_result"] == {"head_m": 42.1}
    assert payload["calculation_trace"] == [{"step": "friction"}]
    assert payload["human_review"]["required"] is True
