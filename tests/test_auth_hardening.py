import base64
import io
import json
import time

import pytest

from api.app import APIApp
from api.auth import AuthContext, Authenticator
from crm.store import InMemoryCRMStore
from integrations.service import InMemoryIntegrationStore
from jobs.store import InMemoryJobStore


def _app(**kw):
    return APIApp(store=InMemoryJobStore(), crm_store=InMemoryCRMStore(),
                  integration_store=InMemoryIntegrationStore(), **kw)


def _call(app, method, path, body=None, headers=None):
    raw = json.dumps(body or {}).encode()
    env = {"REQUEST_METHOD": method, "PATH_INFO": path, "CONTENT_LENGTH": str(len(raw)), "wsgi.input": io.BytesIO(raw)}
    env.update(headers or {})
    out = {}
    data = b"".join(app(env, lambda s, h: out.update(status=s)))
    return out["status"], json.loads(data.decode() or "{}")


def test_dev_headers_rejected_in_production(monkeypatch):
    monkeypatch.setenv("ENGINEERING_ENV", "production")
    monkeypatch.delenv("ENGINEERING_ALLOW_DEV_AUTH", raising=False)
    monkeypatch.setattr("api.app.build_supabase_job_store_from_env", lambda: InMemoryJobStore(), raising=False)
    app = _app()
    status, _ = _call(app, "GET", "/v1/jobs", headers={"HTTP_X_TENANT_ID": "00000000-0000-0000-0000-000000000001"})
    assert status.startswith("401")


def test_dev_headers_still_work_outside_production(monkeypatch):
    monkeypatch.delenv("ENGINEERING_ENV", raising=False)
    status, _ = _call(_app(), "GET", "/v1/jobs", headers={"HTTP_X_TENANT_ID": "tenant-a"})
    assert status.startswith("200")


def _edge_header(**over):
    payload = {"sub": "u1", "tenant_id": "tenant-evil", "role": "owner", "exp": int(time.time()) + 600}
    payload.update(over)
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


def test_forged_edge_header_ignored_when_not_on_vercel(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("ENGINEERING_ENV", raising=False)
    status, _ = _call(_app(), "GET", "/v1/jobs", headers={"HTTP_X_ENGINEERING_AUTH": _edge_header()})
    # Ignored -> falls through to dev auth which needs X-Tenant-ID -> rejected
    assert status.startswith("401")


def test_edge_header_accepted_on_vercel(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    status, _ = _call(_app(), "GET", "/v1/jobs", headers={"HTTP_X_ENGINEERING_AUTH": _edge_header(scopes=["*"])})
    assert status.startswith("200")


class _VerifiedUser(Authenticator):
    def authenticate(self, environ):
        return AuthContext(tenant_id="tenant-a", user_id="user-123", role="owner",
                           auth_method="supabase_jwt", scopes=frozenset({"*"}), email="reviewer@example.com")


def test_approval_records_verified_identity_not_client_supplied_name(monkeypatch):
    monkeypatch.delenv("ENGINEERING_ENV", raising=False)
    app = _app(development_authenticator=_VerifiedUser())
    payload = {"source": "t", "requested_skill_id": "vfd_energy_savings",
               "inputs": {"motor_kw": 75, "annual_hours": 6000, "tariff_per_kwh": 8.5,
                          "speed_reduction_pct": 15, "static_head_fraction": 25}}
    _, job = _call(app, "POST", "/v1/jobs", payload)
    jid = job["job_id"]
    _call(app, "POST", f"/v1/jobs/{jid}/enqueue")
    _call(app, "POST", f"/v1/jobs/{jid}/process")
    status, approved = _call(app, "POST", f"/v1/jobs/{jid}/approve", {"reviewer": "dashboard", "comment": "ok"})
    assert status.startswith("200"), approved
    events = [e for e in app.store.get(jid).events if str(getattr(e, "status", "")).endswith("approved") or (isinstance(e, dict) and e.get("status") == "approved")]
    blob = json.dumps(approved, default=str)
    assert "reviewer@example.com" in blob
    assert "dashboard" not in blob.replace("Approved from Engineering Operations dashboard", "")
