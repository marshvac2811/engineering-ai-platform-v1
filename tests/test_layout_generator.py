import io
import ezdxf
from engineering.layout.generator import build_layout_dxf, plan_layout
from engineering.plan import read_plan
from engineering.plan.samples import office_plan_dxf


def _model():
    return read_plan("plan.dxf", office_plan_dxf(units="mm")).model


def test_layout_places_equipment_inside_every_room():
    m = _model()
    d = plan_layout(m, plant_xy=(-1.5, -1.5))
    assert len(d["rooms"]) == 7
    for it in d["rooms"]:
        assert it["diffusers"] and it["units"] and it["sprinklers"]
    assert d["rooms"][0]["sprinkler_pitch_m"] <= 3.48


def test_layout_dxf_is_layered_deterministic_and_labelled_preliminary():
    m = _model()
    a = build_layout_dxf(m, reference="R1", project="Test")
    b = build_layout_dxf(m, reference="R1", project="Test")
    assert a.dxf == b.dxf
    doc = ezdxf.read(io.StringIO(a.dxf.decode("utf-8")))
    layers = {e.dxf.layer for e in doc.modelspace()}
    assert {"M-DIFF", "M-UNIT", "F-SPKL", "F-PIPE-MAIN", "M-DUCT-TRUNK", "A-WALL"} <= layers
    texts = " ".join(e.dxf.text for e in doc.modelspace() if e.dxftype() == "TEXT")
    assert "PRELIMINARY" in texts and "NOT FOR CONSTRUCTION" in texts
    assert a.summary["sprinklers"] > 0 and a.summary["diffusers"] > 0


def test_layout_refuses_schedule_only_plan():
    import pytest
    from engineering.plan.model import PlanModel, PlanRoom
    m = PlanModel(source_file="s.csv", file_type="csv", rooms=[PlanRoom("R01", "A", [], 20.0)], has_geometry=False)
    with pytest.raises(ValueError):
        plan_layout(m)
