from engineering.building.prose_inputs import design_conditions
from engineering.building.schedule import rooms_text_from_prose, extract_room_schedule

TEXT = """Building: G+3, 4 floors, 12,000 sqm built-up, floor height 3.6 m.
Design conditions: outdoor 43 °C DB / 23 °C WB summer, indoor 24 °C and 50% RH.
Rooms:
Reception, 60 sqm, 10 people
Server room, 30 sqm, 2 people, equipment 500 W/sqm
"""


def test_room_names_and_people_are_kept_and_building_totals_are_not_rooms():
    rooms = extract_room_schedule(rooms_text_from_prose(TEXT))["rooms"]
    assert [r["name"] for r in rooms] == ["Reception", "Server room"]
    assert [r.get("occupancy") for r in rooms] == [10, 2]


def test_design_conditions_are_read_from_the_request():
    c = design_conditions(TEXT)
    assert c["outdoor_db_c"] == 43.0 and 8 < c["outdoor_rh_pct"] < 25
    assert c["room_db_c"] == 24.0 and c["room_rh_pct"] == 50.0
