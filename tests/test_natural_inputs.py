from orchestrator.intake import build_plan


def test_vrf_zone_lines_are_read():
    plan = build_plan("Size a VRF system. Zone A, 120 sqm, 150 W/sqm\nZone B, 80 sqm, 120 W/sqm")
    assert plan.work_items[0].skill_id == "vrf_sizing"
    assert plan.status == "ready_for_execution"


def test_decarbonisation_roadmap_is_not_hijacked_by_study_route():
    plan = build_plan("Prepare a decarbonisation roadmap for an existing 250 TR HVAC plant")
    assert plan.selected_skill_id != "energy_optimisation_study"
