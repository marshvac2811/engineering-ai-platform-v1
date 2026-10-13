import pytest
from skills.common import SkillRequest
from skills.energy.retrofit import retrofit_study
from skills.energy.retrofit.adapter import RetrofitStudySkill

SURVEY = [{"name": "Chiller 1", "type": "chiller", "rated_kw": 200, "load_factor": 0.6, "annual_hours": 4000},
          {"name": "CHW pump", "type": "pump", "rated_kw": 30, "load_factor": 0.8, "annual_hours": 6000}]


def test_survey_baseline_and_efficiency_upgrade_by_hand():
    r = retrofit_study(tariff_per_kwh=8, survey=SURVEY, measures=[
        {"name": "New chiller", "type": "efficiency_upgrade", "survey_item": "Chiller 1", "existing_efficiency": 0.9,
         "new_efficiency": 0.6, "investment": 3000000}])
    assert r["baseline_reconciliation"]["surveyed_kwh"] == 624000          # 200*.6*4000 + 30*.8*6000
    m = r["measures_ranked"][0]
    assert m["annual_saving_kwh"] == pytest.approx(480000 * (1 - 0.6 / 0.9), abs=1)     # 160,000
    assert m["simple_payback_years"] == pytest.approx(3000000 / (160000 * 8), abs=0.01)
    assert m["phase"].startswith("Phase 2") and "Chiller 1" in m["basis"]


def test_reconciliation_warns_beyond_15_percent_and_uses_measured_baseline():
    r = retrofit_study(tariff_per_kwh=8, survey=SURVEY, measured_annual_kwh=900000, measures=[
        {"name": "x", "type": "custom", "annual_savings_kwh": 1000, "investment": 100}])
    assert r["baseline_reconciliation"]["baseline_used"] == "measured" and r["baseline_consumption_kwh"] == 900000
    assert any("differs from the measured bill" in w for w in r["_warnings"])


@pytest.mark.parametrize("bad", [
    {"name": "n", "type": "efficiency_upgrade", "survey_item": "Nope", "existing_efficiency": 1, "new_efficiency": .5, "investment": 1},
    {"name": "n", "type": "efficiency_upgrade", "survey_item": "Chiller 1", "existing_efficiency": .5, "new_efficiency": .9, "investment": 1}])
def test_bad_upgrade_rejected(bad):
    with pytest.raises(ValueError):
        retrofit_study(tariff_per_kwh=8, survey=SURVEY, measures=[bad])


def test_skill_runs_and_validates():
    sk = RetrofitStudySkill()
    ok = sk.run(SkillRequest(skill_id="retrofit_study", inputs={"tariff_per_kwh": 8, "survey": SURVEY, "measures": [
        {"name": "VFD", "type": "vfd", "motor_kw": 30, "speed_reduction_pct": 20, "static_head_fraction": 0.3, "annual_hours": 6000, "investment": 200000}]}))
    assert ok.status == "draft_ready" and ok.engineering_result["phase_summary"]
    assert sk.run(SkillRequest(skill_id="retrofit_study", inputs={})).status == "input_validation_failed"
