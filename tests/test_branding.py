import io
from pypdf import PdfReader
from jobs.service import JobService
from jobs.store import InMemoryJobStore
from orchestrator.intake import build_plan
import openpyxl
from branding import brand, footer_line, logo_svg


def _dispatched():
    st = InMemoryJobStore()
    svc = JobService(st, tenant_id="t")
    job = svc.create_from_plan(build_plan("Please size a duct for 5000 CFM"))
    svc.approve(job.job_id, reviewer="x")
    svc.dispatch(job.job_id)
    return st, job


def test_every_pdf_page_carries_mars_branding_and_address():
    st, job = _dispatched()
    reader = PdfReader(io.BytesIO(st.get_artifact_bytes(job.job_id, "pdf", tenant_id="t")))
    assert len(reader.pages) >= 1
    for page in reader.pages:
        text = page.extract_text()
        assert "MARS ENGINEERING SOLUTIONS" in text
        assert brand()["address"] in text and brand()["email"] in text
    assert reader.metadata.author == "Mars Engineering Solutions"


def test_workbook_sheets_have_print_header_and_footer():
    st, job = _dispatched()
    wb = openpyxl.load_workbook(io.BytesIO(st.get_artifact_bytes(job.job_id, "xlsx", tenant_id="t")))
    for ws in wb.worksheets:
        assert ws.oddHeader.left.text == "MARS ENGINEERING SOLUTIONS"
        assert "Mars Engineering Solutions" in ws.oddFooter.left.text


def test_brand_is_overridable_by_environment(monkeypatch):
    monkeypatch.setenv("MARS_ADDRESS", "Plot 1, Sector 18, Gurugram 122015")
    assert "Plot 1, Sector 18, Gurugram 122015" in footer_line()


def test_logo_svg_is_valid_markup():
    assert logo_svg(32).startswith("<svg") and logo_svg(32).endswith("</svg>")


def test_workbook_has_background_watermark_and_stays_valid():
    import zipfile
    from xml.dom import minidom
    st, job = _dispatched()
    data = st.get_artifact_bytes(job.job_id, "xlsx", tenant_id="t")
    z = zipfile.ZipFile(io.BytesIO(data))
    assert "xl/media/mars_watermark.png" in z.namelist()
    sheets = [n for n in z.namelist() if n.startswith("xl/worksheets/sheet")]
    assert sheets
    for n in z.namelist():
        if n.endswith((".xml", ".rels")):
            minidom.parseString(z.read(n))
    for n in sheets:
        assert z.read(n).decode().count("<picture ") == 1
    openpyxl.load_workbook(io.BytesIO(data))
