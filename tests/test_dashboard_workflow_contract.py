from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app.html"
API = ROOT / "api" / "app.py"


def test_dashboard_file_and_authenticated_api_contract():
    html = APP.read_text(encoding="utf-8")
    assert "engineering_ai_access_token" in html
    assert 'api("/v1/intake"' in html
    assert "/v1/jobs/" in html
    assert "/information" in html
    assert "formatResult" in html
    assert "Dispatch" in html


def test_dashboard_renders_plan_questions_and_unsupported_scope_safely():
    html = APP.read_text(encoding="utf-8")
    assert "engineeringPlan.tasks" in html
    assert "AI Request Understanding" in html
    assert "AI Decision & Evidence" in html
    assert "esc(" in html


def test_api_serves_external_dashboard_file():
    source = API.read_text(encoding="utf-8")
    assert 'Path(__file__).resolve().parents[1] / "web" / "app.html"' in source


def test_dashboard_awaiting_information_message_uses_precise_questions():
    html = APP.read_text(encoding="utf-8")
    assert "const needs=d.job?.orchestration?.questions||d.job?.orchestration?.missing_inputs||[];" in html
    assert 'needs.length?needs.join(" ")' in html
    assert 'The request is waiting for additional information.' in html
    assert 'showMsg(msg,true,"Request submitted successfully.")' in html
