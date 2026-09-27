"""Focused API contract tests for the universal workflow lifecycle."""
import io
import json

from api.app import APIApp
from jobs.store import InMemoryJobStore


def call(app, method, path, body=None, tenant="tenant-a"):
    raw = json.dumps(body or {}).encode("utf-8")
    captured = {}
    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = headers
    environ = {
        "REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": "",
        "CONTENT_LENGTH": str(len(raw)), "wsgi.input": io.BytesIO(raw),
        "HTTP_X_TENANT_ID": tenant,
    }
    result = b"".join(app(environ, start_response))
    return captured["status"], json.loads(result.decode("utf-8"))


class StubAuth:
    def authenticate(self, environ):
        from api.auth import AuthContext
        return AuthContext(tenant_id=environ.get("HTTP_X_TENANT_ID", "tenant-a"), user_id="test-user", role="engineer", scopes={"jobs:read", "jobs:write"}, auth_method="test")


def test_report_route_returns_not_found_before_execution():
    app = APIApp(store=InMemoryJobStore(), development_authenticator=StubAuth())
    status, payload = call(app, "GET", "/v1/jobs/missing/report")
    assert status == "404 Not Found"
    assert payload["error"] == "Report is not available for this job"
