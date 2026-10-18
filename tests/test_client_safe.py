from reports.client_safe import client_safe_bundle
from skills.commercial.boq_takeoff.procure import consolidate_procure, canonical_unit


def test_procure_merges_identical_lines_and_units():
    rows = [
        {"item_no": 1, "description": "Duct Static pressure Sensor", "unit": "Nos.", "quantity": 4},
        {"item_no": 2, "description": "Duct  static pressure sensor", "unit": "Each", "quantity": 6},
        {"item_no": 3, "description": "Chilled water pump", "unit": "Set", "quantity": 2},
    ]
    out = consolidate_procure(rows)
    assert len(out) == 2
    sensor = next(r for r in out if "sensor" in r["description"].lower())
    assert sensor["quantity"] == 10 and sensor["item_nos"] == "1, 2" and sensor["unit"] == "Nos"
    assert canonical_unit("LOT") == "Lot"


def test_client_safe_removes_basis_and_recipes():
    bundle = {"tasks": [{"capability_id": "boq_takeoff", "calculation_trace": [{"step": 1}], "calculations": [{"x": 1}],
                         "assumptions": [{"name": "recipe_factors", "value": "x"}, {"name": "work_programme_basis", "value": "y"}],
                         "warnings": ["Consumption and wastage factors for these recipes are unvalidated defaults: A"],
                         "engineering_result": {"unvalidated_recipes_used": ["A"],
                                                "boq_breakdown": [{"recipe_name": "A", "materials": [{"material_name": "m", "basis": "k x 1.1"}]}],
                                                "procure_as_specified": [{"item_no": 1, "description": "Pump", "unit": "Nos", "quantity": 1}]}}]}
    s = str(client_safe_bundle(bundle)).lower()
    for word in ("recipe", "k x 1.1", "unvalidated", "work_programme_basis", "'step'"):
        assert word not in s
    assert "group" in s
