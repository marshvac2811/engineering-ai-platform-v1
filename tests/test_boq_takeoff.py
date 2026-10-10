import pytest

from scope_engine.analyzer import analyze_scope
from skills.common import SkillRequest
from skills.commercial.boq_takeoff import takeoff, parse_boq_csv
from skills.commercial.boq_takeoff.adapter import BoqTakeoffSkill


def run(**inputs):
    return BoqTakeoffSkill().run(SkillRequest(skill_id="boq_takeoff", inputs=inputs))


def test_area_quantity_in_free_text_is_extracted():
    r = analyze_scope("gypsum partition 1200 sqft in office fitout")
    assert r["work_items"][0]["quantity"] == 1200.0


def test_unit_conversion_and_wastage_hand_checked():
    r = takeoff([{"item_no": "1", "description": "Gypsum partition", "unit": "sqm", "quantity": 100}])
    anchors = next(m for m in r["material_totals"] if m["material_name"] == "Anchors/Fasteners")
    assert anchors["quantity"] == pytest.approx(100 * 10.7639104 * 0.5 * 1.05, abs=0.01)   # 565.1
    tiles = takeoff([{"description": "Vitrified tile flooring", "unit": "sqft", "quantity": 500}])
    cement = next(m for m in tiles["material_totals"] if m["material_name"] == "Cement")
    assert cement["quantity"] == pytest.approx(500 * 4 * 1.05)  # 2100 kg


def test_consolidates_same_material_across_lines():
    r = takeoff([{"item_no": "1", "description": "Vitrified tile flooring", "unit": "sqft", "quantity": 100},
                 {"item_no": "2", "description": "tile flooring", "unit": "sqft", "quantity": 200}])
    cement = next(m for m in r["material_totals"] if m["material_name"] == "Cement")
    assert cement["quantity"] == pytest.approx(300 * 4 * 1.05) and cement["source_items"] == "1, 2"


def test_unmatched_bad_unit_and_bad_quantity_are_reported_not_guessed():
    r = takeoff([{"item_no": "1", "description": "Chiller 100 TR", "unit": "nos", "quantity": 1},
                 {"item_no": "2", "description": "Gypsum partition", "unit": "kg", "quantity": 5},
                 {"item_no": "3", "description": "Gypsum partition", "unit": "sqft", "quantity": "abc"}])
    assert r["matched_line_count"] == 0 and r["unmatched_line_count"] == 3
    assert "cannot convert" in r["unmatched_lines"][1]["reason"]


def test_custom_recipe_overrides_and_is_not_flagged_unvalidated():
    rec = {"id": "paint", "name": "Wall Painting", "base_unit": "sqft", "aliases": ["wall paint"],
           "materials": [{"name": "Emulsion", "unit": "l", "consumption_per_unit": 0.02, "wastage_percent": 10}]}
    r = takeoff([{"description": "Wall painting two coats", "unit": "sqft", "quantity": 1000}], [rec])
    assert r["material_totals"][0]["quantity"] == pytest.approx(22.0) and r["unvalidated_recipes_used"] == []


def test_csv_input_and_skill_warnings():
    csv_text = "item_no,description,unit,quantity\n1,GI duct 24G,sqm,200\n2,AHU,nos,2\n"
    assert len(parse_boq_csv(csv_text)) == 2
    res = run(boq_csv=csv_text)
    assert res.status == "draft_ready"
    assert res.engineering_result["material_totals"][0]["quantity"] == pytest.approx(216.0)
    assert any("unvalidated" in w for w in res.warnings) and any("not taken off" in w for w in res.warnings)


def test_requires_boq():
    assert run().status == "input_validation_failed"


def test_sitetrack_recipe_csv_import_end_to_end():
    recipes_csv = ("work_type,work_unit,material_name,unit,consumption_per_unit,wastage_percent\n"
                   "Gypsum Wall Partition,sqft,Gypsum Board 12mm,sqft,2.1,5\n"
                   "Gypsum Wall Partition,sqft,Screws,nos,4,5\n")
    res = run(boq_items=[{"item_no": "1", "description": "Gypsum Wall Partition L2", "unit": "sqft", "quantity": 1000}],
              recipes_csv=recipes_csv)
    board = next(m for m in res.engineering_result["material_totals"] if m["material_name"] == "Gypsum Board 12mm")
    assert board["quantity"] == pytest.approx(2205.0)
    assert res.engineering_result["unvalidated_recipes_used"] == []


def test_recipe_csv_rejects_bad_rows():
    from skills.commercial.boq_takeoff import parse_recipes_csv
    with pytest.raises(ValueError):
        parse_recipes_csv("work_type,work_unit,material_name,unit,consumption_per_unit,wastage_percent\nX,sqft,,nos,1,0\n")
