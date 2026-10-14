import io
import ezdxf
from engineering.layout.generator import build_layout_dxf
from engineering.layout.sizing import size_ducts, size_sprinkler_mains, split_at_junctions
from engineering.plan import read_plan
from engineering.plan.samples import office_plan_dxf


def test_branch_joining_mid_run_splits_the_trunk_and_accumulates_load():
    segs = [((0, 0), (10, 0)), ((5, 3), (5, 0))]
    assert len(split_at_junctions(segs)) == 3
    res = size_ducts(segs, (0, 0), [((10, 0), 3600.0), ((5, 3), 1800.0)])
    by = {(r["a"], r["b"]): r for r in res["runs"]}
    assert by[((0, 0), (5, 0))]["airflow_m3h"] == 5400      # carries both terminals
    assert by[((5, 0), (10, 0))]["airflow_m3h"] == 3600
    assert by[((5, 0), (5, 3))]["airflow_m3h"] == 1800
    assert all(r["velocity_ms"] <= 6.0 for r in res["runs"])
    assert res["critical_loss_pa"] > 0


def test_sprinkler_schedule_and_hydraulic_flag():
    res = size_sprinkler_mains([((0, 0), (10, 0))], (0, 0), [((10, 0), 8)])
    assert res["runs"][0]["size"] == "DN50"
    big = size_sprinkler_mains([((0, 0), (10, 0))], (0, 0), [((10, 0), 150)])
    assert "hydraulic" in big["runs"][0]["note"]


def test_layout_dxf_carries_sizes_and_summary():
    m = read_plan("plan.dxf", office_plan_dxf(units="mm")).model
    out = build_layout_dxf(m, plant_xy=(-1.5, -1.5))
    sz = out.summary["sizing"]
    assert sz["duct_trunk"]["by_size"] and sz["sprinkler_main"]["by_size"]
    doc = ezdxf.read(io.StringIO(out.dxf.decode("utf-8")))
    texts = " ".join(e.dxf.text for e in doc.modelspace() if e.dxftype() == "TEXT")
    assert "dia (" in texts and "heads)" in texts and "PRELIMINARY" in texts
