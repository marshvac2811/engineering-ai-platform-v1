"""Scheduled Gmail sync: secret-protected, fail-closed, de-duplicating."""
import pytest

from api.app import APIApp
from crm.store import InMemoryCRMStore
from integrations.service import InMemoryIntegrationStore
from jobs.store import InMemoryJobStore
from tests.test_integration_api import FakeGmailClient, call

SECRET = "s" * 32
PATH = "/v1/integrations/gmail/sync-scheduled"


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.setenv("GMAIL_SCHEDULER_SECRET", SECRET)
    monkeypatch.setenv("GMAIL_SCHEDULER_TENANT_ID", "00000000-0000-0000-0000-000000000001")
    monkeypatch.setenv("GMAIL_SYNC_QUERY", "label:engineering-requests is:unread")
    from ingestion.service import IngestionService
    from integrations.providers.gmail import TrialGmailTokenStore
    return APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(), integration_store=InMemoryIntegrationStore(),
                  ingestion=IngestionService(), gmail_client=FakeGmailClient(), gmail_token_store=TrialGmailTokenStore(str(tmp_path / "t")))


def test_scheduled_sync_creates_job_once(app):
    status, body = call(app, "POST", PATH, headers={"HTTP_X_SCHEDULER_SECRET": SECRET})
    assert status == "200 OK" and body["query"] == "label:engineering-requests is:unread"
    assert body["results"][0]["job_created"] is True
    status, body = call(app, "POST", PATH, headers={"HTTP_X_SCHEDULER_SECRET": SECRET})
    assert status == "200 OK" and body["results"][0]["created"] is False and body["results"][0]["job_created"] is False


@pytest.mark.parametrize("headers", [{}, {"HTTP_X_SCHEDULER_SECRET": "wrong" * 8}, {"HTTP_X_SCHEDULER_SECRET": ""}])
def test_scheduled_sync_rejects_missing_or_wrong_secret(app, headers):
    # A normal admin (dev headers) must not be able to use the scheduler endpoint either.
    status, body = call(app, "POST", PATH, headers=headers)
    assert status.startswith("401") or status.startswith("403"), (status, body)


def test_scheduled_sync_fails_closed_without_explicit_query(app, monkeypatch):
    monkeypatch.delenv("GMAIL_SYNC_QUERY")
    status, body = call(app, "POST", PATH, headers={"HTTP_X_SCHEDULER_SECRET": SECRET})
    assert status.startswith("400") and "GMAIL_SYNC_QUERY" in body["error"]


def test_short_secret_is_never_accepted(app, monkeypatch):
    monkeypatch.setenv("GMAIL_SCHEDULER_SECRET", "short")
    status, _ = call(app, "POST", PATH, headers={"HTTP_X_SCHEDULER_SECRET": "short"})
    assert status.startswith("401") or status.startswith("403")
