from orchestrator.intake import build_plan

TEXT = """HVAC design package, room by room load, airflow, duct sizing and equipment schedule for an office building in New Delhi.
Rooms:
Reception, 60 sqm, 10 people
Open office, 250 sqm, 60 people
Select chiller or VRF with standby, chilled water pump head, duct sizes and AHU/FCU schedule."""


def test_full_design_package_request_is_not_taken_over_by_duct_sizing():
    plan = build_plan(TEXT)
    assert plan.work_items[0].skill_id == "hvac_design_package"
    assert plan.status == "ready_for_execution"
