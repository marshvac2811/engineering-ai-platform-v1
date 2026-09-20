from integrations.service import IntegrationService, InMemoryIntegrationStore
from integrations.providers.gmail import normalize_message
from integrations.providers.upwork import authorization_url
from integrations.providers.gumroad import normalize_event
from integrations.providers.fiverr import normalize_event as fiverr_event


def test_gmail_normalization():
    event = normalize_message(tenant_id="t1", message={
        "id": "m1", "threadId": "th1", "payload": {
            "headers": [
                {"name": "Subject", "value": "Load Calculation Request"},
                {"name": "From", "value": "client@example.com"},
            ],
            "body": {},
            "parts": [{"filename": "plans.pdf", "mimeType": "application/pdf", "body": {"attachmentId": "a1", "size": 10}}],
        },
    })
    assert event["provider"] == "gmail"
    assert event["payload"]["subject"] == "Load Calculation Request"
    assert event["payload"]["attachments"][0]["filename"] == "plans.pdf"


def test_provider_oauth_and_normalization():
    url = authorization_url("client", "https://example.com/callback", state="s1", code_challenge="abc")
    assert "response_type=code" in url
    assert "code_challenge=abc" in url
    assert normalize_event(tenant_id="t1", event={"sale_id": "s1"})["provider"] == "gumroad"
    assert fiverr_event(tenant_id="t1", event={"order_id": "o1"})["external_event_id"] == "o1"


def test_event_deduplication_and_connection_registry():
    service = IntegrationService(InMemoryIntegrationStore(), tenant_id="t1")
    conn = service.configure(provider="gmail", status="connected", scopes=["mail.read"])
    assert conn.status == "connected"
    first, created = service.ingest(provider="gmail", event_type="message.received", external_event_id="m1", payload={"subject": "Load"})
    second, created2 = service.ingest(provider="gmail", event_type="message.received", external_event_id="m1", payload={"subject": "Load"})
    assert created is True and created2 is False
    assert first.external_event_id == second.external_event_id
