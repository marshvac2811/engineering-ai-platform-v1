from engineering.building_mep.design import design_building
from engineering.building_mep.boq import generate_boq
from engineering.building_mep.schedule import floors_from_text
from skills.common import SkillRequest
from skills.mep.building_package.adapter import MEPBuildingPackageSkill

ROOMS = [{"name": "Open office", "area_m2": 250, "occupancy": 60}, {"name": "Cabin", "area_m2": 25, "occupancy": 4}]


def test_floors_text_blocks_and_repeat():
    f = floors_from_text("Floor: Typical x4\nOpen office | 250 sqm | 60 people\nFloor: Ground\nLobby | 100 sqm | 20 people")
    assert [(x["name"], x["count"]) for x in f] == [("Typical", 4), ("Ground", 1)]


def test_design_scales_with_floor_repeat():
    one = design_building(building_type="office", climate_zone="composite", floors=[{"name": "F", "count": 1, "rooms": ROOMS}])
    five = design_building(building_type="office", climate_zone="composite", floors=[{"name": "F", "count": 5, "rooms": ROOMS}])
    assert five["floors_total"] == 5 and abs(five["total_area_m2"] - 5 * one["total_area_m2"]) < 1
    assert five["fire"]["sprinkler_heads"] >= 5 * one["fire"]["sprinkler_heads"] - 5
    assert five["electrical"]["floor_distribution_boards"] == 5


def test_boq_takes_off_every_generated_line():
    d = design_building(building_type="office", climate_zone="composite", floors=[{"name": "F", "count": 3, "rooms": ROOMS}])
    r = generate_boq(d)
    assert r["unmatched_line_count"] == 0 and r["material_totals"] and r["procure_as_specified_count"] > 0
    names = " ".join(m["material_name"] for m in r["material_totals"]).lower()
    for word in ("sprinkler", "soil and waste", "conduit", "duct"):
        assert word in names or any(word in l["description"].lower() for l in r["generated_boq_lines"])


def test_skill_requires_rooms_and_flags_unavailable_plan_reading(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    skill = MEPBuildingPackageSkill()
    res = skill.run(SkillRequest(skill_id="mep_building_package", inputs={"building_type": "office"}))
    assert res.status == "input_validation_failed"
    import base64
    res = skill.run(SkillRequest(skill_id="mep_building_package", inputs={"building_type": "office", "plan_image_b64": base64.b64encode(b"x").decode()}))
    assert res.status == "input_validation_failed" and "text" in " ".join(res.validation_errors).lower()


def test_skill_runs_from_text():
    res = MEPBuildingPackageSkill().run(SkillRequest(skill_id="mep_building_package", inputs={
        "building_type": "office", "floor_count": 5, "floors_text": "Open office | 250 sqm | 60 people\nCabin | 25 sqm | 4 people"}))
    assert res.status == "draft_ready" and res.engineering_result["building_summary"]["floors_total"] == 5
