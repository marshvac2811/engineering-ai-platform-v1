import io
import json

from api.app import APIApp


def call(app, method, path, body=None, tenant="tenant-a", user="user-a", role="owner", auth=None):
    raw = b"" if body is None else json.dumps(body).encode()
    headers = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_LENGTH": str(len(raw)),
        "wsgi.input": io.BytesIO(raw),
        "HTTP_X_TENANT_ID": tenant,
        "HTTP_X_USER_ID": user,
        "HTTP_X_USER_ROLE": role,
    }
    if auth:
        headers["HTTP_AUTHORIZATION"] = auth
    captured = {}
    def sr(status, hdrs): captured["status"] = status
    result = b"".join(app(headers, sr))
    return captured["status"], json.loads(result)


def test_control_plane_issue_api_key_and_authenticate():
    app = APIApp()
    scopes = ["jobs:read", "jobs:write", "usage:read"]
    status, payload = call(app, "POST", "/v1/api-keys", {"name": "integration", "role": "engineer", "scopes": scopes})
    assert status == "201 Created"
    secret = payload["secret"]
    assert secret.startswith("eap_live_")

    status, account = call(app, "GET", "/v1/account", auth=f"Bearer {secret}")
    assert status == "200 OK"
    assert account["tenant_id"] == "tenant-a"
    assert account["role"] == "engineer"
    assert account["auth_method"] == "api_key"
    assert set(account["scopes"]) == set(scopes)


def test_scope_enforcement_and_revocation():
    app = APIApp()
    status, payload = call(app, "POST", "/v1/api-keys", {"name": "read-only", "role": "engineer", "scopes": ["jobs:read"]})
    assert status == "201 Created"
    secret = payload["secret"]

    status, _ = call(app, "POST", "/v1/jobs", {"source": "api", "requested_skill_id": "pump_head", "inputs": {}}, auth=f"Bearer {secret}")
    assert status == "403 Forbidden"

    key_id = payload["api_key"]["api_key_id"]
    status, _ = call(app, "POST", f"/v1/api-keys/{key_id}/revoke", {}, role="owner")
    assert status == "200 OK"
    status, _ = call(app, "GET", "/v1/account", auth=f"Bearer {secret}")
    assert status == "401 Unauthorized"


def test_role_enforcement_and_usage_metering():
    app = APIApp()
    status, _ = call(app, "POST", "/v1/jobs", {"source": "api", "requested_skill_id": "pump_head", "inputs": {}})
    assert status == "201 Created"
    job_id = call(app, "POST", "/v1/jobs", {"source": "api", "requested_skill_id": "pump_head", "inputs": {}})[1]["job_id"]
    status, _ = call(app, "POST", f"/v1/jobs/{job_id}/approve", {"comment": "x"}, role="member")
    assert status == "403 Forbidden"
    status, usage = call(app, "GET", "/v1/usage", role="member")
    assert status == "200 OK"
    assert usage["event_count"] >= 3
