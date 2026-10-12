import pytest

from engineering.plan import read_plan
from engineering.plan.samples import office_plan_dxf, office_plan_pdf

EXPECT_ROOM_M2 = 48.0


def _names(model):
    return {r.name for r in model.rooms}


@pytest.mark.parametrize("units", ["mm", "cm", "m"])
def test_dxf_walls_detect_six_rooms_and_corridor_in_any_declared_unit(units):
    res = read_plan("plan.dxf", office_plan_dxf(units=units))
    assert res.status == "partial" and res.model is not None
    m = res.model
    assert len(m.rooms) == 7
    areas = sorted(round(r.area_m2) for r in m.rooms)
    assert areas.count(48) == 7 or sum(1 for a in areas if abs(a - 48) <= 3) == 7
    assert {"OPEN OFFICE", "MEETING ROOM", "CABIN 1", "CONFERENCE", "SERVER ROOM", "CABIN 2", "CORRIDOR"} == _names(m)
    assert m.needs_confirmation is True      # detected from walls, a person must confirm


def test_dxf_room_outlines_are_high_confidence_and_exact():
    res = read_plan("plan.dxf", office_plan_dxf(room_outlines=True))
    m = res.model
    assert res.status == "ok" and len(m.rooms) == 6 and all(r.confidence == "high" for r in m.rooms)
    assert all(abs(r.area_m2 - EXPECT_ROOM_M2) < 0.01 for r in m.rooms)
    assert m.needs_confirmation is False


def test_dxf_without_labels_names_spaces_generically_and_warns():
    res = read_plan("plan.dxf", office_plan_dxf(with_labels=False))
    assert all(r.name.startswith("Space ") for r in res.model.rooms)
    assert res.model.needs_confirmation


def test_unit_override_rescales():
    res = read_plan("plan.dxf", office_plan_dxf(units="mm"), units="m")   # wrong on purpose
    total = sum(r.area_m2 for r in res.model.rooms)
    assert total > 100000          # proves the override is honoured, not silently ignored


def test_pdf_scale_read_from_drawing_text():
    res = read_plan("plan.pdf", office_plan_pdf(scale=100))
    assert res.status == "partial" and res.model
    assert res.model.scale_note.startswith("1:100")
    assert len(res.model.rooms) == 7
    assert all(abs(r.area_m2 - 48) < 3 for r in res.model.rooms)


def test_pdf_without_scale_asks_instead_of_guessing():
    res = read_plan("plan.pdf", office_plan_pdf(scale=100, with_scale_text=False))
    assert res.status == "needs_scale" and res.model is None
    res2 = read_plan("plan.pdf", office_plan_pdf(scale=100, with_scale_text=False), scale=100)
    assert res2.model and len(res2.model.rooms) == 7


def test_schedule_files_have_no_geometry():
    res = read_plan("rooms.csv", b"Room,Area\nOpen office,120 m2\nMeeting room,30 m2\n")
    assert res.status == "ok" and res.model.has_geometry is False and len(res.model.rooms) == 2


def test_unsupported_and_bad_files_explain_themselves():
    assert read_plan("scan.jpg", b"x").status == "unsupported"
    assert read_plan("plan.dwg", b"AC1027").status == "unsupported"
    assert read_plan("x.dxf", b"garbage").status in {"failed"}
    assert read_plan("notes.docx", b"x").status == "unsupported"
