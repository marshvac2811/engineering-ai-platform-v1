from integrations.whatsapp import send_whatsapp
from reports.status_summary import build_status_summary
from tests.test_project_client_and_export import _app, _call


def test_status_summary_text_and_short_version():
    class D:
        def __init__(s, **k):
            s.__dict__.update(dict(name="Rites BOQ", company="RITES", stage="won", value=1000, next_follow_up=None, delivery={}))
            s.__dict__.update(k)
    deals = [D(), D(name="Old lead", stage="quotation", next_follow_up="2020-01-01"), D(name="Paid-up", delivery={"delivered_on": "2026-01-01", "invoice_amount": 100, "outstanding": 40})]
    full, short = build_status_summary([], deals, today="2026-10-15")
    assert "Won, not delivered yet" in full and "Old lead" in full and "Payments outstanding" in full and "Rs 40" in full
    assert len(short) < 1600 and "Full report is in your email" in short


def test_whatsapp_not_configured_is_reported_not_raised(monkeypatch):
    for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM", "STATUS_REPORT_WHATSAPP_TO"):
        monkeypatch.delenv(k, raising=False)
    assert send_whatsapp("hi")["status"] == "not_configured"


def test_endpoint_reports_email_failure_cleanly_and_rate_limits():
    app = _app()
    st, body = _call(app, "POST", "/v1/status-report/send", {})
    assert st.startswith("200") and body["email"]["status"] in ("sent", "failed") and body["whatsapp"]["status"] == "not_configured"
    st2, _ = _call(app, "POST", "/v1/status-report/send", {})
    assert st2.startswith("429")
