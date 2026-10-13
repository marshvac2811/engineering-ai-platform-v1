import io
import openpyxl
import pytest
from skills.commercial.boq_takeoff import takeoff
from skills.commercial.boq_takeoff.xlsx_boq import parse_boq_xlsx


def _book(rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


ROWS = [["Tender"], ["Sl.No", "Description of Work", "No.of Qty", "Units"],
        [1, "DUCT THERMAL & ACOUSTIC INSULATION"], [2, "NS-43.0 Supply and fixing of nitrile rubber insulation"],
        [3, "NS-43.1 19 mm", 100, "Sqmt"], [4, "NS-43.2 25 mm", 50, "Sqmt"],
        [5, "Wall tiles", 200, "sqft"], [6, "Pump set", 2, "Set"], [7, "note without qty"]]


def test_heading_context_carried_to_sublines():
    lines = parse_boq_xlsx(_book(ROWS))
    assert len(lines) == 4
    assert "DUCT THERMAL & ACOUSTIC INSULATION" in lines[0]["description"] and "DUCT THERMAL" in lines[1]["description"]
    assert lines[2]["description"] == "Wall tiles"


def test_takeoff_from_xlsx_with_tender_units():
    r = takeoff(parse_boq_xlsx(_book(ROWS)))
    ids = {x["item_no"]: x["recipe_id"] for x in r["line_takeoff"]}
    assert ids["3"] == ids["4"] == "duct_thermal_insulation" and ids["5"] == "wall_tile_work"
    assert r["unmatched_line_count"] == 0 and r["procure_as_specified_count"] == 1   # pump set is equipment


def test_no_table_is_reported():
    with pytest.raises(ValueError):
        parse_boq_xlsx(_book([["a", "b"], [1, 2]]))


def test_skill_accepts_xlsx_upload_and_rejects_garbage():
    import base64
    from skills.common import SkillRequest
    from skills.commercial.boq_takeoff.adapter import BoqTakeoffSkill
    sk = BoqTakeoffSkill()
    sk.draft_fn = None
    ok = sk.run(SkillRequest(skill_id="boq_takeoff", inputs={"boq_xlsx_b64": base64.b64encode(_book(ROWS)).decode()}))
    assert ok.status == "draft_ready" and ok.engineering_result["matched_line_count"] == 3
    bad = sk.run(SkillRequest(skill_id="boq_takeoff", inputs={"boq_xlsx_b64": base64.b64encode(b"not excel").decode()}))
    assert bad.status == "input_validation_failed"


def test_supply_items_carry_size_and_equipment_with_area_alias_is_listed():
    lines = [{"item_no": "1", "description": "NS-54.0 MV Cable | NS-54.2 3C-6 sq mm Aluminium", "spec": "NS-54.2 3C-6 sq mm Aluminium", "unit": "Metre", "quantity": 100},
             {"item_no": "2", "description": "NS-54.0 MV Cable | NS-54.3 4C-10 sq mm Copper", "spec": "NS-54.3 4C-10 sq mm Copper", "unit": "Metre", "quantity": 50},
             {"item_no": "3", "description": "Non return damper motorised", "unit": "Each", "quantity": 2}]
    r = takeoff(lines)
    names = {m["material_name"]: m["quantity"] for m in r["material_totals"]}
    assert names["Armoured cable 3C-6 sq mm Aluminium"] == 103.0 and names["Armoured cable 4C-10 sq mm Copper"] == 51.5
    assert r["unmatched_line_count"] == 0 and r["procure_as_specified_count"] == 1
