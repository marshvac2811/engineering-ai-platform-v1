from engineering.drawing import facade_elevation, to_dict

def test_parametric_facade_model():
    m = facade_elevation(6000, 3000)
    assert m.validate() == []
    assert len(m.lines) == 4
    assert len(m.dimensions) == 2
    assert to_dict(m)["metadata"]["generation"] == "parametric"

def test_invalid_geometry_is_rejected():
    m = facade_elevation(6000, 3000)
    bad = m.lines[0]
    m.lines[0] = type(bad)(bad.start, bad.start, bad.layer)
    assert any("zero length" in e for e in m.validate())
