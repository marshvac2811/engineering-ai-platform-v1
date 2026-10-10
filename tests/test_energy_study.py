import io
from types import SimpleNamespace

import pytest
from pypdf import PdfReader

from reports.artifacts import build_approved_pdf
from skills.common import SkillRequest
from skills.energy.study import energy_study
from skills.energy.study.adapter import EnergyStudySkill

MEASURES = [
    {"name": "Pump VFD", "type": "vfd", "motor_kw": 30, "speed_reduction_pct": 20, "static_head_fraction": 20,
     "annual_hours": 4000, "investment": 250000},
    {"name": "Rooftop solar", "type": "solar", "capacity_kwp": 100, "investment": 4500000, "annual_om": 40000},
    {"name": "Controls retrofit", "type": "custom", "annual_savings_kwh": 20000, "investment": 100000},
]
INPUTS = {"annual_consumption_kwh": 600000, "tariff_per_kwh": 8.5, "measures": MEASURES}


def test_hand_checked_savings_payback_and_carbon():
    r = energy_study(annual_consumption_kwh=600000, tariff_per_kwh=8.5, measures=MEASURES)
    by = {m["measure"]: m for m in r["measures_ranked"]}
    # VFD: 30 kW x (1 - (0.2 + 0.8 x 0.8^3)) x 4000 h = 46,848 kWh
    assert by["Pump VFD"]["annual_saving_kwh"] == pytest.approx(46848, abs=1)
    assert by["Pump VFD"]["simple_payback_years"] == pytest.approx(250000 / (46848 * 8.5), abs=0.01)
    assert by["Rooftop solar"]["annual_saving_kwh"] == 150000
    assert by["Rooftop solar"]["net_annual_saving"] == 150000 * 8.5 - 40000
    assert r["measures_ranked"][0]["rank_by_payback"] == 1
    assert [m["simple_payback_years"] for m in r["measures_ranked"]] == sorted(m["simple_payback_years"] for m in r["measures_ranked"])
    total = 46848 + 150000 + 20000
    assert r["combined_saving_kwh"] == total
    assert r["baseline_scope2_tco2e"] == pytest.approx(600000 * 0.71 / 1000, abs=0.01)
    assert r["combined_avoided_tco2e_per_year"] == pytest.approx(total * 0.71 / 1000, abs=0.01)


def test_combined_saving_is_capped_at_baseline_with_warning():
    res = EnergyStudySkill().run(SkillRequest(skill_id="energy_optimisation_study", inputs={
        "annual_consumption_kwh": 100000, "tariff_per_kwh": 8, "measures": [
            {"name": "A", "type": "custom", "annual_savings_kwh": 80000, "investment": 1},
            {"name": "B", "type": "custom", "annual_savings_kwh": 80000, "investment": 1}]}))
    assert res.engineering_result["combined_saving_kwh"] == 100000
    assert any("capped" in w for w in res.warnings)


@pytest.mark.parametrize("bad", [
    {"name": "x", "type": "solar", "investment": 1},                 # no capacity
    {"name": "x", "type": "vfd", "investment": 1},                   # missing vfd inputs
    {"name": "x", "type": "magic", "investment": 1, "annual_savings_kwh": 1},
    {"name": "x", "type": "custom", "annual_savings_kwh": 100},      # no investment
])
def test_bad_measures_rejected(bad):
    res = EnergyStudySkill().run(SkillRequest(skill_id="energy_optimisation_study",
                                              inputs={"annual_consumption_kwh": 1000, "tariff_per_kwh": 8, "measures": [bad]}))
    assert res.status == "calculation_failed"


def test_missing_inputs():
    assert EnergyStudySkill().run(SkillRequest(skill_id="energy_optimisation_study", inputs={})).status == "input_validation_failed"


def test_pdf_shows_ranked_measures():
    res = EnergyStudySkill().run(SkillRequest(skill_id="energy_optimisation_study", inputs=INPUTS)).to_dict()
    job = SimpleNamespace(job_id="j1", report_id="r1", status=SimpleNamespace(value="approved"),
                          requested_skill_id="energy_optimisation_study", skill_id="energy_optimisation_study", project_context={})
    bundle = {"manifest": {"schema_version": "engineering-evidence-v1", "bundle_sha256": "a", "input_hash": "b", "source_evidence": []},
              "request": {"source": "t", "inputs": INPUTS},
              "tasks": [{"task_id": "t1", "capability_id": "energy_optimisation_study", "status": "completed", "objective": "Energy study",
                         "inputs": INPUTS, "engineering_result": res["engineering_result"], "calculation_trace": res["calculation_trace"],
                         "assumptions": res["assumptions"], "warnings": res["warnings"], "compliance": [], "skill_version": "1.0.0"}],
              "workflow": {"status": "completed", "blockers": []}, "result": {"status": "completed"}, "review": {"events": []}}
    text = " ".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(build_approved_pdf(job=job, evidence_bundle=bundle))).pages)
    assert "Measures Ranked" in text and "Pump VFD" in text and "Rooftop solar" in text
