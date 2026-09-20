import io
import json
import os
from api.app import APIApp


def call(app, method, path, payload=None, headers=None):
    body = json.dumps(payload or {}).encode()
    env = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": io.BytesIO(body),
        "HTTP_X_TENANT_ID": "00000000-0000-0000-0000-000000000001",
        "HTTP_X_USER_ID": "user-1",
        "HTTP_X_ROLE": "admin",
        "HTTP_X_SCOPES": "integrations:read integrations:write jobs:read jobs:write",
    }
    for k, v in (headers or {}).items():
        env[k] = v
    captured = {}
    def start(status, response_headers):
        captured["status"] = status
        captured["headers"] = response_headers
    chunks = app(env, start)
    return captured["status"], json.loads(b"".join(chunks))


def test_integration_connection_and_event_to_job():
    app = APIApp()
    status, body = call(app, "POST", "/v1/integrations", {"provider": "gmail", "status": "connected"})
    assert status == "201 Created"
    assert body["provider"] == "gmail"

    status, body = call(app, "POST", "/v1/integrations/gmail/events", {
        "external_event_id": "m-100",
        "event_type": "message.received",
        "payload": {"subject": "Load Calculation Request", "body_text": "Please calculate load for this site."},
    })
    assert status == "201 Created"
    assert body["created"] is True
    assert body["job_created"] is True
    assert body["job"]["tenant_id"] == "00000000-0000-0000-0000-000000000001"

    status, body2 = call(app, "POST", "/v1/integrations/gmail/events", {
        "external_event_id": "m-100",
        "event_type": "message.received",
        "payload": {"subject": "Load Calculation Request", "body_text": "duplicate"},
    })
    assert status == "201 Created"
    assert body2["created"] is False
    assert body2["job_created"] is False


def test_webhook_secret_allows_unauthenticated_context():
    os.environ["INTEGRATION_WEBHOOK_SECRET_GUMROAD"] = "secret-1"
    try:
        app = APIApp()
        body = json.dumps({"external_event_id": "sale-1", "payload": {"product_id": "p1"}}).encode()
        env = {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/v1/integrations/gumroad/events",
            "CONTENT_LENGTH": str(len(body)),
            "wsgi.input": io.BytesIO(body),
            "HTTP_X_TENANT_ID": "00000000-0000-0000-0000-000000000001",
            "HTTP_X_INTEGRATION_SECRET": "secret-1",
        }
        captured = {}
        def start(status, headers): captured["status"] = status
        result = json.loads(b"".join(app(env, start)))
        assert captured["status"] == "201 Created"
        assert result["event"]["provider"] == "gumroad"
        assert result["job_created"] is False
    finally:
        os.environ.pop("INTEGRATION_WEBHOOK_SECRET_GUMROAD", None)


def test_gmail_oauth_start_requires_configured_client(monkeypatch):
    monkeypatch.setenv("GMAIL_CLIENT_ID", "client-1")
    monkeypatch.setenv("GMAIL_REDIRECT_URI", "https://example.com/v1/integrations/gmail/oauth/callback")
    app = APIApp()
    status, body = call(app, "GET", "/v1/integrations/gmail/oauth/start", headers={"QUERY_STRING": "login_hint=trial%40example.com"})
    assert status == "200 OK"
    assert body["provider"] == "gmail"
    assert "accounts.google.com/o/oauth2/v2/auth" in body["authorization_url"]
    assert "gmail.readonly" in body["authorization_url"]
    assert "trial%40example.com" in body["authorization_url"]


def test_gmail_normalization_walks_nested_mime_parts():
    import base64
    from integrations.providers.gmail import normalize_message
    enc = lambda text: base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")
    message = {
        "id": "m-200",
        "threadId": "t-200",
        "payload": {
            "headers": [{"name": "Subject", "value": "Duct Sizing Request"}],
            "parts": [{
                "mimeType": "multipart/alternative",
                "parts": [{"mimeType": "text/plain", "body": {"data": enc("Please size 4500 CFM duct.")}}],
            }, {
                "filename": "plan.pdf",
                "mimeType": "application/pdf",
                "body": {"attachmentId": "att-1", "size": 1234},
            }],
        },
    }
    result = normalize_message(tenant_id="00000000-0000-0000-0000-000000000001", message=message)
    assert result["payload"]["subject"] == "Duct Sizing Request"
    assert "4500 CFM" in result["payload"]["body_text"]
    assert result["payload"]["attachments"][0]["attachment_id"] == "att-1"

    from orchestrator.intake import extract_facts
    facts = extract_facts("4500 CFM, rectangular duct, width 600 mm, height 400 mm")
    assert facts["width_mm"] == 600
    assert facts["height_mm"] == 400


class FakeGmailClient:
    def list_message_ids(self, tenant_id, *, q, max_results):
        return [{"id": "m-live-1"}]

    def get_message(self, tenant_id, message_id):
        import base64
        enc = lambda text: base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")
        return {
            "id": message_id,
            "threadId": "thread-1",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Load Calculation Request"},
                    {"name": "From", "value": "client@example.com"},
                ],
                "parts": [
                    {"mimeType": "text/plain", "body": {"data": enc("Please calculate preliminary cooling load.")}},
                    {"filename": "floor-plan.pdf", "mimeType": "application/pdf", "body": {"attachmentId": "att-1", "size": 4}},
                ],
            },
        }

    def get_attachment(self, tenant_id, message_id, attachment_id):
        return b"%PDF-FAKE"

    def profile(self, tenant_id):
        return {"emailAddress": "trial@example.com"}


def test_gmail_live_sync_normalizes_creates_job_and_downloads_attachment(tmp_path):
    from integrations.providers.gmail import TrialGmailTokenStore
    token_store = TrialGmailTokenStore(str(tmp_path / "gmail"))
    token_store.save("00000000-0000-0000-0000-000000000001", {"access_token": "a", "refresh_token": "r", "expires_at": 9999999999})
    app = APIApp(gmail_client=FakeGmailClient(), gmail_token_store=token_store)
    status, body = call(app, "POST", "/v1/integrations/gmail/sync", {"q": "subject:(Load Calculation Request)", "download_attachments": True})
    assert status == "200 OK"
    assert body["messages_seen"] == 1
    assert body["results"][0]["job_created"] is True
    assert body["results"][0]["attachments_downloaded"][0]["filename"] == "floor-plan.pdf"

