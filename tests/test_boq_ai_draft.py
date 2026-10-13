from skills.commercial.boq_takeoff import takeoff


def fake_draft(desc, unit):
    return {"materials": [{"name": "Aluminium section", "unit": "kg", "consumption_per_unit": 1.5, "wastage_percent": 5},
                          {"name": "Bad", "unit": "kg", "consumption_per_unit": "x"},
                          {"name": "Glass 12mm", "unit": "sqft", "consumption_per_unit": 1.0, "wastage_percent": 99}],
            "assumptions": ["12 mm toughened glass"]}


LINE = [{"item_no": "1", "description": "Frameless glass partition 12mm", "unit": "sqft", "quantity": "100"}]


def test_no_draft_fn_stays_unmatched():
    r = takeoff(LINE)
    assert r["unmatched_line_count"] == 1 and not r["ai_drafted_items"]


def test_draft_is_flagged_clamped_and_calculated():
    r = takeoff(LINE, draft_fn=fake_draft)
    assert r["matched_line_count"] == 1 and r["ai_drafted_items"] == ["1"]
    assert r["line_takeoff"][0]["recipe_source"] == "ai_draft"
    tot = {m["material_name"]: m["quantity"] for m in r["material_totals"]}
    assert tot["Aluminium section"] == 157.5          # 100 x 1.5 x 1.05
    assert tot["Glass 12mm"] == 130.0                 # wastage clamped to 30%
    assert "Bad" not in tot and r["unvalidated_recipes_used"]


def test_draft_failure_reported_not_invented():
    def boom(d, u):
        raise RuntimeError("down")
    r = takeoff(LINE, draft_fn=boom)
    assert r["unmatched_line_count"] == 1 and "AI draft failed" in r["unmatched_lines"][0]["reason"]
