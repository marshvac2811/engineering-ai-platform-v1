import pytest
from skills.commercial.boq_takeoff import takeoff

CASES = [("Gypsum ceiling", "gypsum_false_ceiling"), ("Gypsum ceiling tiles work", "gypsum_ceiling_tiles"),
         ("Aluminium partition with partical board".replace("partical", "particle"), "aluminium_partition_particle_board"),
         ("Frameless glass partition 12mm", "frameless_glass_partition"), ("Wall tiles work", "wall_tile_work"),
         ("Floor tile work vitrified tile", "vitrified_tile_flooring")]


@pytest.mark.parametrize("desc,rid", CASES)
def test_matches_and_flags_unvalidated(desc, rid):
    r = takeoff([{"item_no": "1", "description": desc, "unit": "sqft", "quantity": "1000"}])
    assert r["matched_line_count"] == 1 and r["line_takeoff"][0]["recipe_id"] == rid
    assert r["unvalidated_recipes_used"] and r["material_totals"]


def test_sqm_converts():
    r = takeoff([{"item_no": "1", "description": "Wall tiles", "unit": "sqm", "quantity": "10"}])
    assert r["line_takeoff"][0]["recipe_quantity"] == pytest.approx(107.639, abs=0.001)
