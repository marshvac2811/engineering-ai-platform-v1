import base64
import io

import ezdxf

from engineering.services_takeoff.boq_link import apply_drawing, classify_line
from engineering.services_takeoff.measure import measure_dxf, parse_size
from skills.commercial.boq_takeoff import takeoff
from skills.commercial.boq_takeoff.adapter import BoqTakeoffSkill
from skills.common import SkillRequest


def _services_dxf() -> bytes:
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    for layer in ("P-PIPE-WATER", "M-DUCT", "E-CONDUIT", "M-TAG", "P-TAG", "E-TAG", "A-WALL"):
        doc.layers.add(layer)
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (10000, 0), (10000, 5000)], dxfattribs={"layer": "P-PIPE-WATER"})   # 15 m, one 90 elbow
    msp.add_line((4000, 0), (4000, 3000), dxfattribs={"layer": "P-PIPE-WATER"})                      # 3 m branch -> a tee
    msp.add_text("DN50", dxfattribs={"layer": "P-TAG", "insert": (5000, 300), "height": 200})
    msp.add_text("DN25", dxfattribs={"layer": "P-TAG", "insert": (4300, 1500), "height": 200})
    msp.add_lwpolyline([(0, 8000), (6000, 8000), (6000, 10000)], dxfattribs={"layer": "M-DUCT"})     # 8 m duct 400x300, one elbow
    msp.add_text("400x300", dxfattribs={"layer": "M-TAG", "insert": (3000, 8300), "height": 200})
    msp.add_lwpolyline([(0, 12000), (20000, 12000)], dxfattribs={"layer": "E-CONDUIT"})              # 20 m conduit
    msp.add_text("25 mm", dxfattribs={"layer": "E-TAG", "insert": (9000, 12300), "height": 200})
    blk = doc.blocks.new("WC"); blk.add_circle((0, 0), 200)
    msp.add_blockref("WC", (1000, 1000)); msp.add_blockref("WC", (2000, 1000))
    buf = io.StringIO(); doc.write(buf)
    return buf.getvalue().encode()


def test_size_parsing():
    assert parse_size("DN50") == "50" and parse_size("2\" CPVC") == "50" and parse_size("400 x 300") == "400x300" and parse_size("150 dia") == "150" and parse_size("hello") is None


def test_measurement_lengths_fittings_devices():
    m = measure_dxf("s.dxf", _services_dxf())
    assert abs(m.length("plumbing_supply", "50") - 15.0) < 0.01 and abs(m.length("plumbing_supply", "25") - 3.0) < 0.01
    fc = m.fitting_counts("plumbing_supply")
    assert fc["elbow_90"] == 1 and fc["tee"] == 1
    assert abs(m.length("hvac_duct", "400x300") - 8.0) < 0.01 and m.fitting_counts("hvac_duct")["elbow_90"] == 1
    assert abs(m.length("conduit", "25") - 20.0) < 0.01
    assert m.devices == {"water_closet": 2}


def test_boq_lines_are_classified():
    assert classify_line("Supply and fixing 50 mm dia CPVC pipe")["category"] == "plumbing_supply"
    assert classify_line("GI sheet metal rectangular ducting")["category"] == "hvac_duct"
    assert classify_line("Thermal insulation of ducts")["kind"] == "duct_insulation"
    assert classify_line("25 mm PVC conduit concealed")["kind"] == "conduit"
    assert classify_line("Wiring with 1.5 sqmm FRLS copper wire")["kind"] == "wiring"
    assert classify_line("Providing and fixing European water closet")["kind"] == "fixture"
    assert classify_line("Gypsum partition") is None


def test_takeoff_uses_the_drawing_for_services_items():
    lines = [{"item_no": "1", "description": "Supply and fixing 50 mm CPVC water supply pipe", "unit": "m", "quantity": "100"},
             {"item_no": "2", "description": "Supply and fixing 25 mm CPVC water supply pipe", "unit": "m", "quantity": "10"},
             {"item_no": "3", "description": "Providing and fixing GI sheet ducting", "unit": "sqm", "quantity": "10"},
             {"item_no": "4", "description": "Providing and fixing 25 mm PVC conduit", "unit": "m", "quantity": "20"},
             {"item_no": "5", "description": "Wiring with copper wire in conduit", "unit": "m", "quantity": "60"},
             {"item_no": "6", "description": "Providing and fixing European water closet", "unit": "nos", "quantity": "2"}]
    res = takeoff(lines)
    res = apply_drawing(res, lines, measure_dxf("s.dxf", _services_dxf()))
    items = {b["item_no"]: b for b in res["boq_breakdown"]}
    pipe50 = {m["material_name"]: m for m in items["1"]["materials"]}
    assert abs(pipe50["Pipe DN50"]["quantity"] - 15 * 1.05) < 0.01 and pipe50["Elbow 90 DN50"]["quantity"] == 1 and pipe50["Tee DN50"]["quantity"] == 1
    assert "Measured on drawing" in items["1"]["drawing_note"] and "less than the BOQ" in items["1"]["drawing_note"]
    assert abs({m["material_name"]: m for m in items["2"]["materials"]}["Pipe DN25"]["quantity"] - 3 * 1.05) < 0.01
    sheet = next(m for m in items["3"]["materials"] if m["material_name"].startswith("GI sheet"))
    assert abs(sheet["quantity"] - 8 * 1.4 * 1.10) < 0.01
    wire = next(m for m in items["5"]["materials"] if m["material_name"].startswith("Wire"))
    assert abs(wire["quantity"] - 20 * 3 * 1.1) < 0.01
    assert items["6"]["materials"][0]["quantity"] == 2
    assert res["procure_as_specified_count"] == 0 and res["drawing_measured_item_count"] == 6


def test_skill_accepts_a_drawing_and_schedules_it():
    csv = "item_no,description,unit,quantity\n1,Supply and fixing 50 mm CPVC water supply pipe,m,100\n"
    req = SkillRequest(skill_id="boq_takeoff", inputs={"boq_csv": csv, "drawing_dxf_b64": base64.b64encode(_services_dxf()).decode(), "drawing_filename": "plumbing.dxf"})
    out = BoqTakeoffSkill().run(req)
    assert out.status == "draft_ready", out
    r = out.engineering_result
    assert r["drawing_measured_item_count"] == 1 and r["drawing_measurements"] and r["work_programme"]
    bad = BoqTakeoffSkill().run(SkillRequest(skill_id="boq_takeoff", inputs={"boq_csv": csv, "drawing_dxf_b64": "AAAA", "drawing_filename": "x.dwg"}))
    assert any("only DXF" in w for w in bad.warnings)


def test_report_shows_drawing_measurements_in_pdf_and_excel():
    from io import BytesIO
    import openpyxl
    from pypdf import PdfReader
    from tests.test_project_client_and_export import _app, _call
    from reports.artifacts import build_approved_pdf, build_evidence_xlsx
    from reports.evidence import refresh_evidence_bundle
    csv = ("item_no,description,unit,quantity\n1,Supply and fixing 50 mm CPVC water supply pipe,m,100\n"
           "2,Providing and fixing GI sheet ducting,sqm,10\n3,Providing and fixing European water closet,nos,2\n")
    app = _app()
    st, job = _call(app, "POST", "/v1/jobs", {"source": "t", "requested_skill_id": "boq_takeoff",
                                              "inputs": {"boq_csv": csv, "drawing_dxf_b64": base64.b64encode(_services_dxf()).decode(), "drawing_filename": "svc.dxf"}})
    jid = job["job_id"]
    for a in ("enqueue", "process"):
        _call(app, "POST", f"/v1/jobs/{jid}/{a}")
    _call(app, "POST", f"/v1/jobs/{jid}/approve", {"comment": "ok"})
    j = app.store.get(jid)
    bundle = refresh_evidence_bundle(job=j)
    text = "\n".join(p.extract_text() for p in PdfReader(BytesIO(build_approved_pdf(job=j, evidence_bundle=bundle))).pages)
    assert "From drawing" in text and "Measured on drawing" in text and "Elbow 90 DN50" in text
    wb = openpyxl.load_workbook(BytesIO(build_evidence_xlsx(job=j, evidence_bundle=bundle)))
    col = [r[0] for r in wb["BOQ Item Materials"].iter_rows(values_only=True) if r[0]]
    assert any("From drawing" in str(c) for c in col)


def test_condensate_is_not_domestic_water_and_rivals_are_not_split_blindly():
    assert classify_line("Condensate drain piping incl. fittings")["category"] == "hvac_pipe"
    assert classify_line("Black steel fire pipe incl. fittings/supports")["category"] == "fire_pipe"
    assert classify_line("uPVC soil/waste/vent piping")["category"] == "plumbing_drain"
    assert classify_line("Water closets with cistern", "Nos")["kind"] == "fixture"
    lines = [{"item_no": "16", "description": "Cold water CPVC piping", "unit": "m", "quantity": "100"},
             {"item_no": "17", "description": "Hot water PPR piping", "unit": "m", "quantity": "50"}]
    res = apply_drawing(takeoff(lines), lines, measure_dxf("s.dxf", _services_dxf()))
    assert not res.get("boq_breakdown") or all(b["recipe_source"] != "drawing" for b in res["boq_breakdown"])
    assert any("not split" in n for n in res["drawing_notes"])
