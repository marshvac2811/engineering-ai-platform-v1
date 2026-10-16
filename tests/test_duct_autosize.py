import io

import ezdxf

from engineering.services_takeoff.measure import measure_dxf


def _dxf(with_diffusers=True) -> bytes:
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    for layer in ("M-DUCT", "M-DIFFUSER"):
        doc.layers.add(layer)
    msp = doc.modelspace()
    # trunk 20 m along x with two 5 m branches; no size labels anywhere
    msp.add_line((0, 0), (20000, 0), dxfattribs={"layer": "M-DUCT"})
    msp.add_line((10000, 0), (10000, 5000), dxfattribs={"layer": "M-DUCT"})
    msp.add_line((20000, 0), (20000, 5000), dxfattribs={"layer": "M-DUCT"})
    if with_diffusers:
        for x, y in ((10000, 5000), (20000, 5000), (14000, 0), (18000, 0)):
            msp.add_circle((x, y), 150, dxfattribs={"layer": "M-DIFFUSER"})
    buf = io.StringIO(); doc.write(buf)
    return buf.getvalue().encode()


def test_unsized_ducts_stay_unsized_without_airflow():
    m = measure_dxf("d.dxf", _dxf())
    assert m.length("hvac_duct", "unsized") > 29 and m.autosized_m == 0


def test_unsized_ducts_sized_from_diffuser_airflow():
    m = measure_dxf("d.dxf", _dxf(), duct_cmh_per_diffuser=300)
    assert m.length("hvac_duct", "unsized") < 1e-6
    assert abs(m.length("hvac_duct") - 30.0) < 0.1 and m.autosized_m > 29
    sizes = [int(s) for s in m.sizes("hvac_duct")]
    assert len(sizes) >= 2 and max(sizes) > min(sizes)       # larger near the plant, smaller at the ends
    assert any("PRELIMINARY" in w for w in m.warnings)


def test_no_diffusers_warns_and_leaves_unsized():
    m = measure_dxf("d.dxf", _dxf(False), duct_cmh_per_diffuser=300)
    assert m.length("hvac_duct", "unsized") > 29
    assert any("no diffusers" in w for w in m.warnings)
