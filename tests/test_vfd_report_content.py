"""The VFD report must show worked calculation steps, clear labels and units."""
from reports.formatting import split_unit, trace_steps
from skills.energy.vfd import source_calculator as engine
from skills.energy.vfd.adapters import VFDEnergySavingsSkill
from skills.common import SkillRequest


def _run():
    inputs = {"motor_kw": 75, "speed_reduction_pct": 15, "static_head_fraction": 25, "annual_hours": 6000, "tariff_per_kwh": 8.5}
    return VFDEnergySavingsSkill().run(SkillRequest(skill_id="vfd_energy_savings", inputs=inputs, project_context={"jurisdiction": "IN"}))


def test_trace_has_worked_numbers():
    r = _run()
    steps = trace_steps(r.calculation_trace)
    assert len(steps) == 3 and all(s["detail"] for s in steps)
    assert "0.85^3" in steps[0]["detail"] and "38.6%" in steps[0]["detail"]
    assert "28.9%" in steps[1]["detail"]
    assert "130,233" in steps[2]["detail"] and "1,106,979" in steps[2]["detail"]


def test_labels_and_units_are_clear():
    assert split_unit("annual_hours") == ("Annual operating hours", "hours")
    assert split_unit("static_head_fraction")[1] == "%"
    assert split_unit("tariff_per_kwh") == ("Electricity tariff", "currency per kWh")
    label, unit = split_unit("annual_savings_cost_corrected")
    assert "static-head" in label and unit == "currency"
    assert "Pure" not in " ".join(split_unit(k)[0] for k in engine.calculate_energy_savings(75, 15, 25, 6000, 8.5))


def test_worked_steps_match_calculator():
    o = engine.calculate_energy_savings(75, 15, 25, 6000, 8.5)
    ratio = 0.25 + 0.75 * 0.85 ** 3
    assert abs(75 * (1 - ratio) * 6000 - o["annual_savings_kwh_corrected"]) < 1
