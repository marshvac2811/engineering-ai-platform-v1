from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app.html"
API = ROOT / "api" / "app.py"


def test_dashboard_file_and_authenticated_api_contract():
    html = APP.read_text(encoding="utf-8")
    assert "engineering_ai_access_token" in html
    assert 'fetch("/v1/intake"' in html or 'authFetch("/v1/intake"' in html
    assert "/v1/jobs/" in html
    assert "/answers" in html
    assert "/report?include_content=true" in html


def test_dashboard_renders_plan_questions_and_unsupported_scope_safely():
    html = APP.read_text(encoding="utf-8")
    assert "plan.questions" in html
    assert "plan.work_items" in html
    assert "plan.unsupported_scope" in html
    assert "esc(" in html


def test_api_serves_external_dashboard_file():
    source = API.read_text(encoding="utf-8")
    assert 'Path(__file__).resolve().parents[1] / "web" / "app.html"' in source
