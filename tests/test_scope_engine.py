from scope_engine.analyzer import analyze_scope
from skills.commercial.quantity_takeoff import QuantityTakeoffSkill
from skills.common import SkillRequest


def test_scope_engine_matches_multiple_verticals_and_recipes():
    result = analyze_scope("Office fitout: 1000 sqft gypsum partition and 1200 sqft vitrified tile flooring")
    assert {v["id"] for v in result["verticals"]} == {"interiors"}
    assert len(result["work_items"]) == 2
    names = {x["material_name"] for x in result["material_boq"]}
    assert "Gypsum Board 12mm" in names
    assert "Vitrified Tiles" in names


def test_quantity_takeoff_is_deterministic_and_reviewable():
    skill = QuantityTakeoffSkill()
    result = skill.run(SkillRequest("quantity_takeoff", {"request_text": "Provide 1000 sqft gypsum partition"}))
    assert result.status == "calculated"
    materials = result.engineering_result["material_boq"]
    board = next(x for x in materials if x["material_name"] == "Gypsum Board 12mm")
    assert board["quantity"] == 2205.0
    assert result.human_review_required is True


def test_unsupported_scope_is_never_fabricated():
    result = analyze_scope("Provide a fire fighting system for a hotel")
    assert result["verticals"][0]["id"] == "firefighting"
    assert result["material_boq"] == []
    assert result["status"] == "vertical_identified"
