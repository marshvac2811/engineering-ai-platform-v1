import base64
import re
from email import message_from_bytes

from api.app import APIApp
from crm.store import InMemoryCRMStore
from ingestion.service import IngestionService
from integrations.providers.gmail import TrialGmailTokenStore
from integrations.service import InMemoryIntegrationStore
from jobs.store import InMemoryJobStore
from intake_forms import form_for
from tests.test_integration_api import FakeGmailClient, call

PUMP = "Please calculate the pump head for our chilled water system."


class _Mail(FakeGmailClient):
    def __init__(self, text, sender="client@example.com"):
        self.text, self.sender, self.sent = text, sender, []

    def get_message(self, tenant_id, message_id):
        m = super().get_message(tenant_id, message_id)
        enc = lambda t: base64.urlsafe_b64encode(t.encode()).decode().rstrip("=")
        m["payload"]["parts"] = [{"mimeType": "text/plain", "body": {"data": enc(self.text)}}]
        for h in m["payload"]["headers"]:
            if h["name"] == "From":
                h["value"] = f"Mr Rao <{self.sender}>"
        return m

    def send_message(self, tenant_id, *, raw_b64url, thread_id=None):
        self.sent.append(message_from_bytes(base64.urlsafe_b64decode(raw_b64url)))
        return {"id": "s1"}


def _app(tmp_path, mail):
    ts = TrialGmailTokenStore(str(tmp_path / "g"))
    ts.save("00000000-0000-0000-0000-000000000001", {"access_token": "a", "refresh_token": "r", "expires_at": 9999999999})
    return APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(), integration_store=InMemoryIntegrationStore(),
                  ingestion=IngestionService(), gmail_client=mail, gmail_token_store=ts)


def _sync(app):
    st, body = call(app, "POST", "/v1/integrations/gmail/sync", {"q": "x", "download_attachments": False})
    assert st == "200 OK"
    return body["results"][0]


def test_enquiry_gets_form_automatically_and_answers_run_the_job(tmp_path):
    mail = _Mail(PUMP)
    app = _app(tmp_path, mail)
    r = _sync(app)
    assert r["form"] == "sent" and len(mail.sent) == 1
    body = mail.sent[0].get_payload(decode=True).decode()
    token = re.search(r"/form/([\w-]+)", body).group(1)
    assert "pump head" in body.lower() and "Dear Mr Rao" in body
    assert "default" not in body.lower() and "margin" not in body.lower()
    st, spec = call(app, "GET", f"/v1/public/forms/{token}")
    assert st == "200 OK" and spec["open"] and any(f["key"] == "flow_m3hr" for f in spec["fields"])
    assert "margin_pct" not in [f["key"] for f in spec["fields"]]
    # a wrong answer is rejected with a plain message and the job stays open
    st, bad = call(app, "POST", f"/v1/public/forms/{token}", {"answers": {"flow_m3hr": "abc"}})
    assert st.startswith("400") and bad["problems"]
    good = {"flow_m3hr": "120", "diameter_mm": "150", "straight_length_m": "200", "static_head_m": "15"}
    st, ok = call(app, "POST", f"/v1/public/forms/{token}", {"answers": good})
    assert st == "200 OK" and ok["ok"]
    st, jobs = call(app, "GET", "/v1/jobs")
    assert jobs["jobs"][0]["status"] == "human_review"
    # the form no longer accepts changes once the job has moved on
    st, again = call(app, "POST", f"/v1/public/forms/{token}", {"answers": good})
    assert st == "200 OK" and "already have" not in again["message"] and "Thank you" in again["message"]
    st, jobs = call(app, "GET", "/v1/jobs")
    assert jobs["jobs"][0]["status"] == "human_review"


def test_unknown_token_is_not_found(tmp_path):
    app = _app(tmp_path, _Mail(PUMP))
    st, _ = call(app, "GET", "/v1/public/forms/" + "x" * 30)
    assert st.startswith("404")
    st, _ = call(app, "GET", "/v1/public/forms/short")
    assert st.startswith("404")


def test_no_reply_and_automated_senders_never_get_a_form(tmp_path):
    mail = _Mail(PUMP, sender="noreply@vendor.com")
    r = _sync(_app(tmp_path, mail))
    assert "skipped" in r["form"] and not mail.sent


def test_marketplace_enquiry_is_prepared_for_pasting_not_emailed(tmp_path):
    mail = _Mail(PUMP, sender="someone@messages.upwork.com")
    app = _app(tmp_path, mail)
    r = _sync(app)
    assert "marketplace" in r["form"] and not mail.sent and "/form/" in r["form_url"]
    st, gaps = call(app, "GET", "/v1/intake-gaps")
    assert st == "200 OK" and len(gaps["marketplace_messages"]) == 1
    assert r["form_url"] in gaps["marketplace_messages"][0]["message"]


def test_recent_send_guard_blocks_a_second_form_to_the_same_sender(tmp_path):
    from datetime import datetime, timezone
    from intake_forms.autosend import _recent_to
    from jobs.service import JobService
    from orchestrator.intake import build_plan
    svc = JobService(InMemoryJobStore(), tenant_id="t")
    job = svc.create_from_plan(build_plan(PUMP))
    job.project_context["client_form"] = {"sent_to": "a@b.com", "sent_at": datetime.now(timezone.utc).isoformat()}
    svc.store.save(job)
    assert _recent_to(svc, "a@b.com") and not _recent_to(svc, "c@d.com")


def test_request_matching_no_skill_gets_no_form(tmp_path):
    mail = _Mail("Design a thermal energy storage ice tank for a 1200 TR district cooling plant")
    r = _sync(_app(tmp_path, mail))
    assert not mail.sent and r["form"] in {"not needed", "no client form for this skill"}
